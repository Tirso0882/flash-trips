import os

import uvicorn


def main() -> None:
    uvicorn.run(
        "flash_trips.composition:create_app",
        factory=True,
        host=os.environ.get("HOST", "127.0.0.1"),
        port=int(os.environ.get("PORT", "8000")),
        proxy_headers=False,
        server_header=False,
    )


if __name__ == "__main__":
    main()
