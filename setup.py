from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="MessageCannon",
    version="1.0.0",
    author="Muhammad Faraz",
    author_email="farazgoal@gmail.com",
    description="Professional WhatsApp bulk messaging tool for small businesses",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/farazgoal/MessageCannon",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    classifiers=[
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.11",
        "License :: OSI Approved :: MIT License",
        "Operating System :: Microsoft :: Windows",
        "Environment :: X11 Applications :: GTK",
        "Topic :: Communications",
        "Development Status :: 4 - Beta",
    ],
    python_requires=">=3.11",
    install_requires=[
        "customtkinter>=5.2.0",
        "pandas>=2.0.0",
        "openpyxl>=3.1.0",
        "pywhatkit>=5.4",
        "selenium>=4.15.0",
        "pillow>=10.0.0",
        "qrcode>=7.4",
        "reportlab>=4.0.0",
        "schedule>=1.2.0",
        "python-dotenv>=1.0.0",
        "requests>=2.31.0",
        "apscheduler>=3.10.0",
    ],
    entry_points={
        "console_scripts": [
            "messagecannon=main:main",
        ],
    },
)
