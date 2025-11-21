# Spoopy Buyback 2 - EVE Online Buyback Calculator

Welcome to Spoopy Buyback 2, the buyback calculator for the EVE Online corporation "Spoopy Newbies." This tool helps members of the Spoopy Newbies corporation calculate buyback prices for items they wish to sell to the corporation.

## Table of Contents

- [About](#about)
- [Getting Started](#getting-started)
  - [Prerequisites](#prerequisites)
  - [Installation](#installation)
- [Usage](#usage)
- [Configuration](#configuration)
- [Contributing](#contributing)
- [License](#license)

## About

Spoopy Buyback 2 is a web-based tool designed to streamline the process of calculating buyback prices for items sold to Spoopy Newbies, an EVE Online corporation. Members can use this calculator to estimate the value of their items before selling them to the corporation.

## Getting Started

### Running tests

```bash
pytest --ds=config.settings.test
```

### Prerequisites

- [Docker](https://www.docker.com/) [version]
- [Docker Compose](https://docs.docker.com/compose/) [version]

### Installation

1. Clone the repository:

   ```bash
   git clone https://github.com/your-username/spoopy-buyback-2.git

2. Navigate to the project directory:

cd spoopy-buyback-2

3. Create a .env file in the root directory and add the necessary environment variables:
all of them are required

SECRET_KEY=
ALLOWED_HOSTS=
DEBUG=
DJANGO_SETTINGS_MODULE=config.settings.development

NGINX_PORT=80

DB_NAME=
DB_USERNAME=
DB_PASSWORD=
DB_HOSTNAME=
DB_PORT=5432

POSTGRES_USER=
POSTGRES_PASSWORD=
POSTGRES_DB=

CELERY_BROKER_URL=redis://redis:6379/0

REDIS_BACKEND=redis://redis:6379/0

4. Run the Docker Compose command to start the services:

docker-compose up -d

5. Open a web browser and go to http://localhost:80 to access Spoopy Buyback 2.

Usage
To use Spoopy Buyback 2:

[Provide step-by-step instructions on how to use the buyback calculator. Include screenshots if possible.]
[Explain how to input items, calculate prices, and get results.]
Configuration
[Explain any configuration settings that users need to be aware of. This could include customization options, settings for EVE Online APIs, etc.]

Contributing
Contributions are welcome! If you'd like to contribute to the project, please follow these steps:

Fork the repository.
Create a new branch: git checkout -b feature-name.
Make your changes and commit them: git commit -am 'Add some feature'.
Push to the branch: git push origin feature-name.
Create a pull request.
Please make sure to update tests and documentation as appropriate.

License
[Specify the license under which your project is published. For example: MIT License, Apache License, etc.]

[Optional: Add badges or shields indicating build status, license, etc.]

Created by Firmware.


Feel free to copy and paste this template into your project's `README.md` file, and replace placeholders with the actual information relevant to your project.


# django-docker-template

Start a Production-Ready Dockerized Django Project: https://dev.to/documatic/start-a-production-ready-dockerized-django-project-5eop 
