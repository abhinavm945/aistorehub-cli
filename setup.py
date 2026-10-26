from pathlib import Path
from setuptools import setup, find_packages

this_directory = Path(__file__).parent
readme_path = this_directory / "README.md"
long_description = readme_path.read_text(encoding="utf-8") if readme_path.exists() else ""

setup(
    name="aistorehub",
    version="0.1.8",
    description="The Official CLI for AIStoreHub - Discover, pull, publish, and configure AI systems and MCP servers.",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://aistorehub.in",
    project_urls={
        "Documentation": "https://aistorehub.in/docs",
        "CLI Reference": "https://aistorehub.in/cli",
        "Platform": "https://aistorehub.in",
    },
    author="AIStoreHub Team",
    author_email="abhinav@aistorehub.in",
    license="MIT",
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Topic :: Software Development :: Build Tools",
        "Topic :: Scientific/Engineering :: Artificial Intelligence",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Operating System :: OS Independent",
        "Environment :: Console",
    ],
    keywords="ai, mcp, model-context-protocol, agents, prompts, aistorehub, claude, cursor",
    packages=find_packages(),
    install_requires=[
        "click>=8.0.0",
        "httpx>=0.25.0",
        "keyring>=24.0.0",
    ],
    entry_points={
        "console_scripts": [
            "aihub=sihub.main:cli",
            "aistorehub=sihub.main:cli",
            "sihub=sihub.main:cli",
            "sistorehub=sihub.main:cli",
        ],
    },
    python_requires=">=3.9",
)
