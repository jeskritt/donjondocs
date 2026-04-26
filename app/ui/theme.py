"""
AI Helper Docstring
Purpose: Provides reusable CSS classes, Color blocks, and HTML styling elements uniformly for all NiceGUI instances.
Interactions:
- Included on practically every `.py` file rendering UI. Sets up `ui.add_head_html`.
"""

"""Shared theme, layout, and styling for NiceGUI pages.

Provides a consistent look across all pages with dark mode,
modern typography, and a responsive layout system.
"""

from contextlib import contextmanager

from nicegui import app, ui


# Shared inline style for dialog cards across pages and sheet components.
DIALOG_CARD_STYLE = "background:#1E1E2E;border:1px solid #4F46E5;border-radius:12px;"


def apply_auth_background():
    """Emit the shared .auth-bg gradient block used on login/register pages."""
    ui.add_css('''
        .auth-bg {
            min-height: 100vh;
            background: linear-gradient(135deg, #13131D 0%, #1a1a2e 50%, #16213e 100%);
            display: flex;
            align-items: center;
            justify-content: center;
        }
        .auth-bg::before {
            content: '';
            position: fixed;
            top: 0; left: 0; right: 0; bottom: 0;
            background:
                radial-gradient(ellipse at 20% 50%, rgba(79, 70, 229, 0.08) 0%, transparent 50%),
                radial-gradient(ellipse at 80% 20%, rgba(16, 185, 129, 0.05) 0%, transparent 50%);
            pointer-events: none;
        }
    ''')


# Color palette
COLORS = {
    "primary": "#4F46E5",       # Indigo-600
    "primary_dark": "#3730A3",  # Indigo-800
    "primary_light": "#818CF8", # Indigo-400
    "accent": "#10B981",        # Emerald-500
    "surface": "#1E1E2E",       # Dark surface
    "surface_light": "#2A2A3C", # Slightly lighter surface
    "bg": "#13131D",            # Deep background
    "text": "#E2E8F0",          # Slate-200
    "text_muted": "#94A3B8",    # Slate-400
    "danger": "#EF4444",        # Red-500
    "warning": "#F59E0B",       # Amber-500
}


def apply_global_styles():
    """Apply global CSS styles and font imports."""
    ui.add_head_html('''
        <link rel="preconnect" href="https://fonts.googleapis.com">
        <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
        <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
    ''')

    ui.add_css('''
        :root {
            --primary: #4F46E5;
            --primary-dark: #3730A3;
            --primary-light: #818CF8;
            --accent: #10B981;
            --surface: #1E1E2E;
            --surface-light: #2A2A3C;
            --bg: #13131D;
            --text: #E2E8F0;
            --text-muted: #94A3B8;
            --danger: #EF4444;
            --warning: #F59E0B;
        }

        body {
            font-family: 'Inter', sans-serif !important;
            background-color: var(--bg) !important;
        }

        .nicegui-content {
            padding: 0 !important;
        }

        /* Auth card glassmorphism */
        .auth-card {
            background: rgba(30, 30, 46, 0.8) !important;
            backdrop-filter: blur(20px) !important;
            border: 1px solid rgba(79, 70, 229, 0.2) !important;
            border-radius: 16px !important;
            padding: 2.5rem !important;
            width: 100% !important;
            max-width: 420px !important;
            box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.5) !important;
        }

        /* Page content area */
        .page-content {
            padding: 2rem;
            max-width: 1200px;
            margin: 0 auto;
            width: 100%;
        }

        /* Stat card */
        .stat-card {
            background: rgba(30, 30, 46, 0.6) !important;
            backdrop-filter: blur(10px) !important;
            border: 1px solid rgba(79, 70, 229, 0.15) !important;
            border-radius: 12px !important;
            padding: 1.5rem !important;
            transition: transform 0.2s ease, border-color 0.2s ease !important;
        }

        .stat-card:hover {
            transform: translateY(-2px) !important;
            border-color: rgba(79, 70, 229, 0.4) !important;
        }

        /* Role badges */
        .role-badge {
            padding: 0.25rem 0.75rem;
            border-radius: 9999px;
            font-size: 0.75rem;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.05em;
        }

        .role-admin { background: rgba(239, 68, 68, 0.15); color: #EF4444; }
        .role-premium { background: rgba(245, 158, 11, 0.15); color: #F59E0B; }
        .role-standard { background: rgba(16, 185, 129, 0.15); color: #10B981; }

        /* Data table styling */
        .q-table__container {
            background: rgba(30, 30, 46, 0.6) !important;
            border-radius: 12px !important;
            border: 1px solid rgba(79, 70, 229, 0.15) !important;
        }

        /* Responsive */
        @media (max-width: 768px) {
            .auth-card {
                margin: 1rem !important;
                padding: 1.5rem !important;
            }
            .page-content {
                padding: 1rem;
            }
        }
    ''')


def role_badge_html(role: str) -> str:
    """Generate HTML for a role badge."""
    return f'<span class="role-badge role-{role}">{role}</span>'


@contextmanager
def page_frame(title: str = ""):
    """Context manager providing the standard page layout with header and content area."""
    ui.dark_mode(True)
    apply_global_styles()

    if title:
        ui.page_title(f"{title} — DonjonDocs")
    else:
        ui.page_title("DonjonDocs")

    yield


def notify_error(message: str):
    """Show an error notification."""
    ui.notify(message, type="negative", position="top", close_button=True)


def notify_success(message: str):
    """Show a success notification."""
    ui.notify(message, type="positive", position="top", close_button=True)
