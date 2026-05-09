# LuminaFinance: Project Abstract

## Overview
LuminaFinance is a lightweight, high-performance personal finance dashboard designed to provide users with a comprehensive view of their financial health. The application allows users to track income and expenses, monitor asset portfolios, and manage categorized transactions through an intuitive, single-page interface. 

## Architecture
The project adopts a monolithic architecture, neatly separating the presentation layer from the business logic while remaining within a single repository for easy deployment and management.

- **Frontend (Presentation Layer):** Built using a vanilla web stack (HTML5, CSS3, JavaScript). It operates as a Single Page Application (SPA), utilizing the native `fetch` API to communicate asynchronously with the backend. This approach ensures a fast, responsive user experience without the overhead of heavy JavaScript frameworks.
- **Backend (Application Layer):** Powered by Python and the Django framework. It utilizes the Django REST Framework (DRF) to expose robust RESTful API endpoints for the frontend. The backend is responsible for secure user authentication, business logic execution, and serving the static frontend assets.
- **Database (Persistence Layer):** The data layer leverages Django's Object-Relational Mapper (ORM), allowing for flexible database management. It defaults to SQLite for frictionless local development and is configured to seamlessly transition to a MySQL 8 (3NF) relational database for production environments via environment variables.

## Key Features
- **Interactive Dashboard:** A dynamic, vanilla JS-driven interface for visualizing financial data.
- **Transaction Management:** Categorized tracking of expenses and income.
- **Portfolio Tracking:** Management of diverse asset classes (e.g., Cash, Stocks, Crypto, Real Estate).
- **Environment Adaptability:** Ready for both local testing and production deployment out-of-the-box.
- **Developer-Friendly Seeding:** Includes custom management scripts to populate mock data for rapid testing and demonstration.

## Conclusion
LuminaFinance demonstrates a clean, maintainable approach to full-stack web development. By combining the rapid development capabilities of Django with the lightweight nature of vanilla frontend technologies, the project delivers a scalable and efficient platform for personal financial management.
