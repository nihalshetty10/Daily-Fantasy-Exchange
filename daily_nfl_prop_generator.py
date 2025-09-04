#!/usr/bin/env python3
import logging
from datetime import datetime

from ml.nfl_model import NFLModel


def main() -> int:
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    logger = logging.getLogger(__name__)
    logger.info("🏈 Generating today's NFL props...")
    model = NFLModel(logger=logger)
    out = model.generate_todays_props()
    logger.info(
        "✅ NFL props ready: %s players across %s games at %s",
        out.get('total_players'), out.get('total_games'), out.get('generated_at')
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


