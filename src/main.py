"""PSBTv145-LAB desktop entry point: python src/main.py."""

def main() -> int:
    from ui.main_window import run

    return run()


if __name__ == "__main__":
    raise SystemExit(main())
