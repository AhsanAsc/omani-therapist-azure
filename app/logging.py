import logging, sys

def configure_logging():
    handler = logging.StreamHandler(sys.stdout)
    formatter = logging.Formatter(
        fmt='%(asctime)s %(levelname)s %(name)s: %(message)s',
        datefmt='%Y-%m-%dT%H:%M:%S%z'
    )
    handler.setFormatter(formatter)
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    root.handlers.clear()
    root.addHandler(handler)
