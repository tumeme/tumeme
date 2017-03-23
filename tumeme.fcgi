#!/usr/bin/env python3

from flup.server.fcgi import WSGIServer
from tumeme import create_app

if __name__ == '__main__':
    application = create_app()
    WSGIServer(application).run()
