#!/bin/bash

# Install Python dependencies
pip install -r requirements.txt

# Install Playwright browsers & system dependen
playwright install
playwright install-deps
