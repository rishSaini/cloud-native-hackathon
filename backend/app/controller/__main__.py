"""Entry point: python -m app.controller"""

import logging
import signal

from app.controller import rooms  # noqa: F401, I001  (registers first: taints before placing)
from app.controller import placement  # noqa: F401  (registers the placement reconciler)
from app.controller.loop import Controller
from app.k8s.client import core_api, namespace


def main() -> None:
    from app.controller import insights  # noqa: F401  (K17: registers last, after placement)

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    logging.getLogger("kubernetes").setLevel(logging.WARNING)
    controller = Controller(core_api(), namespace())
    signal.signal(signal.SIGTERM, lambda *_: controller.stop.set())
    controller.start_health_server()
    logging.getLogger("affinity.controller").info(
        "controller started: namespace=%s reconcilers=%s",
        controller.namespace, [name for name, _ in controller.reconcilers],
    )
    controller.run()


if __name__ == "__main__":
    main()
