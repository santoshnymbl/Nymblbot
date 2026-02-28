"""Shared test fixtures for NymblBot tests"""
import os
import pytest
import tempfile
from pathlib import Path


@pytest.fixture
def sample_wiki_content():
    """Sample markdown content for testing chunking and retrieval"""
    return """# Company Overview

Nymbl is a technology company founded in 2022.

## Leadership Team

### CEO / Co-Founder

John Smith is the CEO of Nymbl. He leads company strategy.

### CTO

Jane Doe is the CTO. She oversees all technology decisions.

## Policies

### PTO Policy

Employees get 15 days of PTO per year. Submit PTO requests through the HR portal.

For absences of 5 or more days, manager approval is required in advance.

### India Holiday Calendar

India office observes Republic Day (Jan 26), Independence Day (Aug 15), and Gandhi Jayanti (Oct 2).

## Glossary

- WGLL: What Good Looks Like
- WBLL: What Bad Looks Like
- SA: Solution Architect
- BDR: Business Development Representative
"""


@pytest.fixture
def sample_handbook_content():
    """Sample handbook content for testing multi-file retrieval"""
    return """# Hello, Nymblings

# Company Overview

At Nymbl, we are reimagining the way applications are designed and developed.

## Nymbl Tenets

Be Client Focused: Deliver client value
Be Productive: Focus on optimizing internal processes
Be Improving: Constant improvement on yourself and the team
Be Transparent: Full transparency to employees, clients and investors
Be Balanced: Spend time on personal life and your foundation
Be Reliable: No shallow commitments; full ownership of responsibilities
Be Empowering: Constant enablement of clients and employees
"""


@pytest.fixture
def temp_data_dir(sample_wiki_content, sample_handbook_content):
    """Create a temporary data directory with sample documents"""
    with tempfile.TemporaryDirectory() as tmpdir:
        wiki_path = Path(tmpdir) / "nymbl_wiki.md"
        wiki_path.write_text(sample_wiki_content, encoding="utf-8")

        handbook_path = Path(tmpdir) / "nymbl_handbook.md"
        handbook_path.write_text(sample_handbook_content, encoding="utf-8")

        yield tmpdir
