"""stdout logging only — Vercel functions must never write to disk."""
import logging
import sys

logging.basicConfig(stream=sys.stdout, level=logging.INFO,
                    format="%(asctime)s %(levelname)s %(name)s %(message)s")


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
