from setuptools import setup, find_packages

setup(
    name="guardiannode-sdk",
    version="1.0.0",
    description="GuardianNode — child safety moderation SDK for gaming platforms",
    packages=find_packages(),
    python_requires=">=3.10",
    install_requires=[
        "httpx>=0.27",
        "websocket-client>=1.8",
    ],
    extras_require={
        "async": ["httpx>=0.27"],
    },
)
