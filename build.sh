#!/bin/bash

# Install Python dependencies
pip install -r requirements.txt

# Install Playwright browsers & system dependencies
playwright install
playwright install-deps
