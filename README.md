 # Africa University Agricultural Products Website

## Project Overview

The Africa University Agricultural Products Website is a web-based e-commerce platform designed to enable Africa University to efficiently market and sell its agricultural products online. The system improves accessibility, communication, and digital management of agricultural goods such as vegetables, fruits, dairy products, poultry products, and crops.

## Project Goal

To develop a fully functional agricultural e-commerce platform that enables Africa University to manage, advertise, and sell agricultural products online while ensuring usability, scalability, security, and real-world agricultural accuracy.

---

# Project Team Structure

This project is developed using a structured GitHub workflow with clearly defined roles and responsibilities.

## Development Team

### Elson – Frontend Developer

Responsible for:

* User Interface (UI) design
* Product display pages
* Shopping cart interface
* Responsive layouts and styling

### Theophany – Frontend Developer

Responsible for:

* Navigation system
* Forms and user interactions
* Mobile responsiveness
* Frontend support and integration

### Tendesai – Database Engineer

Responsible for:

* Database design
* Table relationships
* Data storage and retrieval
* Data integrity and optimization

### Kimberely – E-commerce Features Developer

Responsible for:

* Shopping cart functionality
* Checkout process
* Product ordering workflow
* Transaction processing logic

### Christisen – Admin & Security Developer

Responsible for:

* User authentication
* Role-based access control
* Admin dashboard functionality
* System security implementation

### Nyasha – Agribusiness Representative (Product Integrity & Validation)

Responsible for:

* Validating product categories
* Verifying agricultural product descriptions
* Reviewing pricing accuracy
* Monitoring stock level realism
* Ensuring alignment with Africa University agricultural operations
* Providing agricultural domain expertise and feedback

### Tanaka – Project Lead, Documentation & Testing

Responsible for:

* Project coordination and oversight
* System documentation (README, reports, user guides)
* Feature testing and quality assurance
* Bug tracking and issue management
* Pull request review and approval
* GitHub workflow management
* Final deployment coordination

---

# Development Workflow

## Main Branch (main)

* Production-ready code only
* No direct commits allowed
* Receives code only from approved pull requests

## Development Branch (dev)

* Integration branch for completed features
* All pull requests are merged here first
* Used for testing before production deployment

## Feature Branches

Each feature must be developed in its own branch.

Examples:

* feature-login
* feature-product-ui
* feature-cart
* feature-checkout
* feature-admin-dashboard

---

# Git Workflow Process

All contributors must follow this workflow:

```bash
git pull origin dev

git checkout -b feature-name

# Work on your feature

git add .

git commit -m "Describe feature implemented"

git push origin feature-name
```

Then:

1. Create a Pull Request to the `dev` branch.
2. Request review from the Project Lead.
3. Address any requested changes.
4. Merge into `dev` after approval.
5. Features in `dev` are tested before eventual merge into `main`.

---

# Quality Assurance Process

Before merging into `main`:

* All features must be tested.
* No critical bugs should remain.
* Documentation must be updated.
* Agribusiness validation must be completed.
* Pull requests must be reviewed and approved.

---

# Expected Deliverables

* Responsive Agricultural E-commerce Website
* Product Catalog Management
* Shopping Cart System
* User Authentication System
* Admin Dashboard
* Database System
* Documentation and Testing Reports
* Deployment to Production Environment


