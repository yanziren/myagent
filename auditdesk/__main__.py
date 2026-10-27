from auditdesk.api.app import create_app


def main() -> None:
    import uvicorn

    from pathlib import Path

    db = Path(__file__).resolve().parents[1] / "data" / "auditdesk.sqlite"
    uvicorn.run(create_app(db_path=str(db)), host="127.0.0.1", port=8765)


if __name__ == "__main__":
    main()
