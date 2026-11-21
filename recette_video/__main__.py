import os

import uvicorn


def main() -> None:
    hote = os.environ.get("HOST", "127.0.0.1")
    port = int(os.environ.get("PORT", "8000"))
    print(f"Application disponible sur http://{hote}:{port}")
    uvicorn.run("recette_video.app:app", host=hote, port=port)


if __name__ == "__main__":
    main()
