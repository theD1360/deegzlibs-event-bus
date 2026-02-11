from setuptools import find_packages, setup

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="deegzlibs-event-bus",
    version="1.0.0",
    author="Diego Alejos",
    author_email="lego.admin@gmail.com",
    description="A small event bus with pluggable queue adapters (e.g. AWS SQS)",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/deegzlibs/deegzlibs",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
    ],
    python_requires=">=3.8",
    install_requires=[
        "pydantic>=2.0",
    ],
    extras_require={
        "sqs": ["boto3"],
        "rabbitmq": ["pika>=1.0"],
        "redis": ["redis>=4.0"],
        "dev": [
            "pytest>=7.0.0",
            "pytest-cov>=4.0.0",
            "pytest-asyncio>=0.21.0",
        ],
    },
)
