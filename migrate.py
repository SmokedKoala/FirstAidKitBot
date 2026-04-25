from migration_control import apply_migrations


def main() -> None:
    applied = apply_migrations()
    if not applied:
        print("No new migrations.")
        return
    print(f"Applied migrations: {', '.join(str(v) for v in applied)}")


if __name__ == "__main__":
    main()
