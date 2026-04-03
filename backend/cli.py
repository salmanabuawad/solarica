
import argparse
from app.parser import run

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--file", required=True)
    args = parser.parse_args()

    with open(args.file, "r", encoding="utf-8", errors="ignore") as f:
        text = f.read()

    result = run(text)
    print(result)

if __name__ == "__main__":
    main()
