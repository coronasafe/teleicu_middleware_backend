#!/bin/bash

daphne -b 0.0.0.0 -p 8090 middleware.asgi:application
