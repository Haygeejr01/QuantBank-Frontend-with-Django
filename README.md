# NeuroBank

<div align="center">

**A Modern Fintech Banking Dashboard**

_Built with Django & Cutting-Edge Frontend Technologies_

[![Python](https://img.shields.io/badge/Python-3.12+-blue?style=flat-square&logo=python)](https://python.org)
[![Django](https://img.shields.io/badge/Django-5.1+-green?style=flat-square&logo=django)](https://djangoproject.com)
[![License](https://img.shields.io/badge/License-MIT-yellow?style=flat-square)](LICENSE)

</div>

---

## Overview

**NeuroBank** is a sophisticated, full-stack fintech banking dashboard that demonstrates modern web development best practices. It features a sleek, responsive UI inspired by contemporary banking apps like OPay, with emphasis on user experience, privacy, and seamless transaction flows.

This project showcases:

- **Full-stack development** with Django backend and vanilla HTML/CSS/JS frontend
- **Responsive design** with mobile-first approach and adaptive layouts
- **Real-time UI interactions** including theme toggling, balance masking, and network detection
- **Secure transaction flows** with account verification and atomic database operations

---

## Features

### Core Banking

- **Multi-Account Management**: Support for multiple bank accounts (Access Bank, Polaris Bank)
- **Smart Transfers**: OPay-style transfer flow with:
  - Automatic bank discovery based on account number
  - Real-time recipient name resolution
  - Secure authorization and confirmation
- **Transaction History**: Complete ledger with debit/credit tracking

### Payments & Services

- **Airtime Recharge**: Quick-select grid with network auto-detection (MTN, GLO, Airtel, 9Mobile)
- **Data Bundle Purchase**: OPay-style data plan selection
- **Bills & Payments**: Utility, subscription, and educational payments

### AI Assistant

- **Neuro AI**: Integrated AI chat assistant for:
  - Spending analysis and insights
  - Credit trajectory predictions
  - Security scans and anomaly detection

### UI/UX Excellence

- **Dark/Light Theme**: Professional toggle with smooth transitions
- **Balance Privacy**: Eye toggle to mask sensitive financial information
- **Responsive Design**: Optimized for desktop, tablet, and mobile
- **Modern Aesthetics**: Glassmorphism, gradients, and micro-animations

---

## Technology Stack

| Category     | Technology                                          |
| ------------ | --------------------------------------------------- |
| **Backend**  | Python 3.12+, Django 5.1                            |
| **Database** | SQLite (development), PostgreSQL (production-ready) |
| **Frontend** | HTML5, CSS3 (Vanilla), JavaScript (ES6+)            |
| **Design**   | CSS Variables, Flexbox, CSS Grid                    |
| **Fonts**    | Google Fonts (Outfit)                               |
| **Charts**   | Chart.js                                            |

---

## Getting Started

### Prerequisites

- Python 3.12 or higher
- pip (Python package manager)
- Git

### Installation

1. **Clone the repository**

   ```bash
   git clone https://github.com/yourusername/neurobank.git
   cd neurobank
   ```

2. **Create a virtual environment**

   ```bash
   python -m venv venv

   # Windows
   venv\Scripts\activate

   # macOS/Linux
   source venv/bin/activate
   ```

3. **Install dependencies**

   ```bash
   pip install django
   ```

4. **Run migrations**

   ```bash
   python manage.py migrate
   ```

5. **Create a test user (optional)**

   ```bash
   python create_test_user.py
   ```

6. **Start the development server**

   ```bash
   python manage.py runserver
   ```

7. **Open your browser**
   ```
   http://127.0.0.1:8000/
   ```

---

## Project Structure

```
mybankapp/
├── accounts/                   # Main Django app
│   ├── templates/accounts/     # HTML templates
│   │   ├── base.html          # Base template
│   │   ├── dashboard.html     # Main dashboard
│   │   ├── dashboard_layout.html  # Layout wrapper
│   │   ├── neuro_ai.html      # AI assistant
│   │   ├── bills.html         # Bills & payments
│   │   ├── profile.html       # User profile
│   │   └── ...
│   ├── models.py              # Database models
│   ├── views.py               # View controllers
│   └── urls.py                # URL routing
├── banking_system/            # Django project settings
│   ├── settings.py
│   └── urls.py
├── static/
│   └── css/
│       └── style.css          # Main stylesheet
├── templates/                 # Global templates
├── manage.py
└── README.md
```

---

## API Endpoints

| Endpoint                    | Method | Description                      |
| --------------------------- | ------ | -------------------------------- |
| `/api/lookup/`              | GET    | Account holder lookup            |
| `/api/discover-banks/`      | GET    | Discover banks by account number |
| `/api/transfer/`            | POST   | Execute transfer                 |
| `/api/service-payment/`     | POST   | Process airtime/data/bills       |
| `/api/deposit/`             | POST   | Process deposit                  |
| `/api/transaction-history/` | GET    | Get transaction history          |

---

## Key Implementation Highlights

### 1. OPay-Style Transfer Flow

- Account number entry triggers automatic bank discovery
- Real-time recipient name resolution via AJAX
- Atomic transactions with database locking

### 2. Privacy-First Design

- Balance masking persisted via localStorage
- Global toggle affects all financial displays
- No sensitive data in URL parameters

### 3. Responsive Architecture

- CSS Grid and Flexbox for layouts
- Media queries for breakpoint handling
- Off-canvas sidebar for mobile navigation

### 4. Theme System

- CSS custom properties for theming
- Smooth transitions between modes
- Theme preference persisted client-side

---

## Future Enhancements

- Push notifications for transactions
- Biometric authentication
- QR code payments
- Investment portfolio tracking
- Multi-currency support
- API rate limiting and caching

---

## Author

**Yemi**  
Full-Stack Developer | Fintech Enthusiast

---

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

## Acknowledgments

- Design inspiration from OPay, Kuda, and modern banking apps
- Django documentation and community
- Chart.js for data visualization

---

<div align="center">

**Built with passion and dedication**

</div>
