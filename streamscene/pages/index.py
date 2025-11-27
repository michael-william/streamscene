"""Landing page for StreamScene with interactive watching eyes."""

import os
from urllib.parse import urlencode
import reflex as rx

from .base_state import BaseState


class IndexState(BaseState):
    """State for landing page."""

    def on_mount(self):
        """Redirect authenticated users to dashboard."""
        if self.user_id:
            return rx.redirect("/dashboard")


# JavaScript for eye tracking and blinking
EYE_TRACKING_SCRIPT = """
(function() {
    const maxMove = 15;

    function trackEye(eye, mouseX, mouseY) {
        if (!eye) return;
        const rect = eye.getBoundingClientRect();
        const eyeCenterX = rect.left + rect.width / 2;
        const eyeCenterY = rect.top + rect.height / 2;
        const deltaX = mouseX - eyeCenterX;
        const deltaY = mouseY - eyeCenterY;
        const angle = Math.atan2(deltaY, deltaX);
        const distance = Math.min(maxMove, Math.hypot(deltaX, deltaY));
        const moveX = Math.cos(angle) * distance;
        const moveY = Math.sin(angle) * distance;
        eye.style.transform = `translate(${moveX}px, ${moveY}px)`;
    }

    function setupTracking() {
        const leftEye = document.getElementById('eye-left');
        const rightEye = document.getElementById('eye-right');

        if (!leftEye || !rightEye) {
            setTimeout(setupTracking, 100);
            return;
        }

        document.addEventListener('mousemove', (e) => {
            trackEye(leftEye, e.clientX, e.clientY);
            trackEye(rightEye, e.clientX, e.clientY);
        });

        document.addEventListener('touchmove', (e) => {
            if (e.touches.length > 0) {
                const touch = e.touches[0];
                trackEye(leftEye, touch.clientX, touch.clientY);
                trackEye(rightEye, touch.clientX, touch.clientY);
            }
        });

        function blink(eye) {
            eye.style.transform = eye.style.transform + ' scaleY(0.1)';
            setTimeout(() => {
                eye.style.transform = eye.style.transform.replace(' scaleY(0.1)', '');
            }, 100);
        }

        function startBlinking() {
            blink(leftEye);
            setTimeout(() => blink(rightEye), 50);
            const nextBlink = Math.random() * 3000 + 2000;
            setTimeout(startBlinking, nextBlink);
        }

        startBlinking();
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', setupTracking);
    } else {
        setupTracking();
    }
})();
"""


def index() -> rx.Component:
    """Landing page with watching eyes effect."""
    # Build OAuth URL directly (no WebSocket needed)
    client_id = os.getenv("OAUTH_CLIENT_ID")
    redirect_uri = os.getenv("OAUTH_REDIRECT_URI")
    auth_url = os.getenv("OAUTH_AUTHORIZATION_URL")

    # Build OAuth authorization URL
    params = {
        "response_type": "code",
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "scope": "openid profile email",
    }
    oauth_url = f"{auth_url}?{urlencode(params)}"

    # Eye style (glowing orb)
    eye_style = {
        "position": "absolute",
        "width": "50px",
        "height": "50px",
        "background": "radial-gradient(circle, white 0%, rgba(255,255,255,0.8) 40%, rgba(200,200,255,0.4) 70%, transparent 100%)",
        "border_radius": "50%",
        "box_shadow": "0 0 20px rgba(255,255,255,0.8), 0 0 40px rgba(150,150,255,0.5), 0 0 60px rgba(100,100,200,0.3)",
        "top": "25%",
        "transition": "transform 0.05s linear",
    }

    return rx.box(
        # Left eye
        rx.box(
            id="eye-left",
            style={**eye_style, "left": "42%"},
        ),
        # Right eye
        rx.box(
            id="eye-right",
            style={**eye_style, "left": "54%"},
        ),
        # Main content card
        rx.box(
            rx.vstack(
                # Title with gradient effect
                rx.heading(
                    "StreamScene",
                    size="9",
                    style={
                        "background": "linear-gradient(135deg, white 0%, #a0a0a0 100%)",
                        "background_clip": "text",
                        "-webkit-background-clip": "text",
                        "color": "transparent",
                        "letter_spacing": "0.1em",
                    },
                ),
                rx.text(
                    "Your Semi-Invasive Message Board",
                    size="5",
                    color="gray",
                    style={"letter_spacing": "0.05em"},
                ),
                rx.text(
                    "They are watching.",
                    size="3",
                    style={"color": "rgba(180, 180, 200, 0.8)", "margin_top": "0.5em"},
                ),
                rx.spacer(height="1.5em"),
                rx.link(
                    rx.button(
                        "Sign In",
                        size="3",
                        color_scheme="blue",
                    ),
                    href=oauth_url,
                    is_external=True,
                ),
                spacing="3",
                align="center",
            ),
            style={
                "position": "absolute",
                "bottom": "20%",
                "left": "50%",
                "transform": "translateX(-50%)",
                "padding": "2em 3em",
                "background": "rgba(20, 20, 30, 0.85)",
                "backdrop_filter": "blur(10px)",
                "border_radius": "16px",
                "border": "1px solid rgba(100, 100, 150, 0.3)",
                "box_shadow": "0 8px 32px rgba(0, 0, 0, 0.4), 0 0 60px rgba(80, 80, 200, 0.15)",
            },
        ),
        # Eye tracking script
        rx.script(EYE_TRACKING_SCRIPT),
        # Full screen container styles
        style={
            "width": "100%",
            "min_height": "100vh",
            "position": "relative",
            "background": "linear-gradient(180deg, #0a0a12 0%, #0d0d18 50%, #05050a 100%)",
            "overflow": "hidden",
        },
        on_mount=IndexState.on_mount,
    )
