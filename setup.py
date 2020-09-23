import setuptools

with open("README.md", "r") as readme:
    long_description = readme.read()

setuptools.setup(
    name="tezos_net_viz",
    version="0.0.1a",
    author="Simon Zeng",
    author_email="simon.zeng@tqtezos.com",
    description="Tezos blockchain visualization tool",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/tqtezos/tezos-net-viz",
    packages=setuptools.find_packages(),
    entry_points={"console_scripts": ["tezos_net_viz=tezos_net_viz:main"]},
    classifiers=[
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "License :: OSI Approved :: BSD License",
        "Operating System :: OS Independent",
    ],
    install_requires=["aiohttp", "pygraphviz"],
    python_requires=">=3.8",
)
