import json
from decimal import Decimal

from app.extensions import db
from app.models import AuditLog, RubricCriterion, Submission
from app.services.judging import JudgingError, _total_score
from app.services.time import utc_now


class ResultsError(ValueError):
    pass


def _event_settings(event):
    try:
        settings = json.loads(event.settings_json or "{}")
    except (TypeError, ValueError):
        settings = {}
    if not isinstance(settings, dict):
        settings = {}
    return settings


def results_are_published(event):
    return bool(_event_settings(event).get("results_published", False))


def aggregate_results(event):
    criteria = RubricCriterion.query.filter_by(
        event_id=event.id, is_active=True
    ).order_by(RubricCriterion.display_order.asc(), RubricCriterion.id.asc()).all()
    submissions = Submission.query.filter_by(event_id=event.id).join(
        Submission.team
    ).order_by(Submission.id.asc()).all()
    rows = []
    if not criteria:
        return [
            {
                "submission": submission,
                "team": submission.team,
                "judge_count": 0,
                "average_score": None,
                "rank": None,
            }
            for submission in submissions
        ]
    for submission in submissions:
        submitted_evaluations = [
            evaluation
            for evaluation in submission.evaluations
            if evaluation.status == "submitted"
        ]
        judge_scores = []
        for evaluation in submitted_evaluations:
            scores = {score.criterion_id: score.score for score in evaluation.scores}
            if any(criterion.id not in scores for criterion in criteria):
                continue
            try:
                total = _total_score(
                    criteria,
                    {criterion.id: Decimal(str(scores[criterion.id])) for criterion in criteria},
                )
            except (JudgingError, ValueError, ArithmeticError):
                continue
            judge_scores.append(total)
        average = (
            (sum(judge_scores, Decimal("0")) / len(judge_scores)).quantize(
                Decimal("0.0001")
            )
            if judge_scores
            else None
        )
        rows.append(
            {
                "submission": submission,
                "team": submission.team,
                "judge_count": len(judge_scores),
                "average_score": average,
                "rank": None,
            }
        )
    ranked = sorted(
        (row for row in rows if row["average_score"] is not None),
        key=lambda row: (
            -row["average_score"],
            row["team"].name.casefold(),
            row["submission"].id,
        ),
    )
    previous_score = None
    previous_rank = None
    for position, row in enumerate(ranked, start=1):
        if previous_score is not None and row["average_score"] == previous_score:
            row["rank"] = previous_rank
        else:
            row["rank"] = position
            previous_rank = position
            previous_score = row["average_score"]
    return sorted(
        rows,
        key=lambda row: (
            row["rank"] is None,
            row["rank"] if row["rank"] is not None else 0,
            row["team"].name.casefold(),
            row["submission"].id,
        ),
    )


def set_results_publication(actor, event, published):
    if actor.role != "organizer" or actor.event_id != event.id:
        raise ResultsError("You are not authorized to publish results for this event.")
    settings = _event_settings(event)
    previous = bool(settings.get("results_published", False))
    settings["results_published"] = bool(published)
    if published:
        settings["results_published_at"] = utc_now().isoformat()
    else:
        settings.pop("results_published_at", None)
    event.settings_json = json.dumps(settings, sort_keys=True)
    db.session.add(
        AuditLog(
            event_id=event.id,
            actor_user_id=actor.id,
            action="results.published" if published else "results.unpublished",
            entity_type="event_results",
            entity_id=event.id,
            before_json=json.dumps({"published": previous}),
            after_json=json.dumps({"published": bool(published)}),
            created_at=utc_now(),
        )
    )
    db.session.commit()
    return bool(published)
