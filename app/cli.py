from app.services.seed import seed_database


def register_cli(app):
    @app.cli.command("seed")
    def seed_command():
        summary = seed_database()
        print("Seed complete (synthetic sample data).")
        for key, value in summary.items():
            print(f"{key}: {value}")
