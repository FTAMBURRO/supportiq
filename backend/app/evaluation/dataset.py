"""Fictional demo dataset for classifier evaluation (Fase 3 · M2).

36 tickets, 6 categories x 6: 100% invented workplace scenarios. No
real people, employers, institutions or support data anywhere — nothing
from UBA, SIU, Mapuche or any real organization, nothing scraped.

Roughly two thirds are clear-cut cases and one third deliberately
borderline (renewal invoices, printers, permissions, quotes) so the
evaluation numbers stay honest instead of flattering. The tuple is
fixed and ordered: evaluation must be reproducible run to run.

Format: ``(title, description, category slug)``.
"""

from __future__ import annotations

REQUESTER_EMAIL = "ana.dev@supportiq.local"  # created by ``flask seed``

DEMO_CATEGORY_SLUGS = (
    "access",
    "hardware",
    "software",
    "network",
    "billing",
    "other",
)

DEMO_TICKETS: tuple[tuple[str, str, str], ...] = (
    # --- access: accounts, logins, permissions ---
    (
        "Password reset email never arrives",
        "I requested a password reset three times and no email shows up "
        "in my inbox or the spam folder.",
        "access",
    ),
    (
        "Account locked after failed logins",
        "My account was locked after typing the wrong password a few "
        "times and I need it unlocked.",
        "access",
    ),
    (
        "New colleague needs access to the shared drive",
        "A new team member starts on Monday and needs permissions on the "
        "shared department folder.",
        "access",
    ),
    (
        "Authenticator code rejected at login",
        "The authenticator app shows a fresh code but the login page "
        "says the code is invalid.",
        "access",
    ),
    (
        "Access denied to the project folder",
        "Opening the shared project directory returns an access denied "
        "message for my account.",
        "access",
    ),
    (
        "Publish button disabled on the intranet",
        "I should publish team announcements but the publish button stays "
        "disabled for my account.",
        "access",
    ),
    # --- hardware: laptops, monitors, peripherals ---
    (
        "Laptop battery drains in half an hour",
        "The battery barely lasts thirty minutes at low brightness with "
        "no heavy applications open.",
        "hardware",
    ),
    (
        "Second monitor is not detected",
        "The external monitor stays black and the laptop does not list it "
        "among the available displays.",
        "hardware",
    ),
    (
        "Keyboard keys stop responding",
        "Several keys on my laptop keyboard need a hard press or do not "
        "respond at all.",
        "hardware",
    ),
    (
        "Docking station drops the monitor",
        "When I dock the laptop the screen flickers and sometimes the "
        "monitor disconnects entirely.",
        "hardware",
    ),
    (
        "Wireless mouse freezes randomly",
        "The wireless mouse stops moving for a few seconds at a time and "
        "then recovers on its own.",
        "hardware",
    ),
    (
        "Fan runs at full speed all day",
        "The cooling fan gets very loud even when only a single browser "
        "window is open.",
        "hardware",
    ),
    # --- software: applications and installations ---
    (
        "Spreadsheet app crashes on open",
        "The spreadsheet application closes immediately whenever I try to "
        "open any file.",
        "software",
    ),
    (
        "Installer fails during update",
        "Installing the latest release fails with a permissions error "
        "halfway through the process.",
        "software",
    ),
    (
        "Calendar invites not syncing",
        "Meetings accepted on my phone never appear in the desktop "
        "calendar application.",
        "software",
    ),
    (
        "Intranet portal loads a blank page",
        "The internal portal shows a blank white page only in my "
        "browser; colleagues see it fine.",
        "software",
    ),
    (
        "PDF export produces an empty file",
        "Exporting a report to PDF finishes successfully but the "
        "resulting file is zero kilobytes.",
        "software",
    ),
    (
        "Chat client stuck reconnecting",
        "The team chat client stays in a reconnecting loop ever since "
        "the last update.",
        "software",
    ),
    # --- network: connectivity, VPN, Wi-Fi ---
    (
        "Office Wi-Fi drops every few minutes",
        "The wireless network disconnects repeatedly through the morning "
        "and I have to reconnect manually.",
        "network",
    ),
    (
        "File server unreachable from my desk",
        "Mapping the network drive fails; the file server does not "
        "answer ping requests from my workstation.",
        "network",
    ),
    (
        "Internal sites fail on DNS",
        "Opening internal sites by name times out while typing the IP "
        "address directly works fine.",
        "network",
    ),
    (
        "Internet slow every afternoon",
        "Pages take forever to load after lunch for everyone on our "
        "floor, then recover by the evening.",
        "network",
    ),
    (
        "Guest Wi-Fi rejects new devices",
        "Visitors cannot join the guest wireless network; the connection "
        "attempt simply times out.",
        "network",
    ),
    (
        "Shared printer offline for my floor",
        "The shared printer is shown as offline although colleagues "
        "upstairs can print to it.",
        "network",
    ),
    # --- billing: invoices and payments ---
    (
        "Duplicate charge on the last invoice",
        "We were billed twice for the same subscription period on the "
        "September invoice.",
        "billing",
    ),
    (
        "Invoice sent to the old address",
        "Please resend the invoice to our new finance mailbox; the "
        "previous address bounces back.",
        "billing",
    ),
    (
        "Invoice missing our purchase order number",
        "The invoice does not include our PO number and accounting will "
        "not process it without one.",
        "billing",
    ),
    (
        "Refund still not received",
        "The credit note was issued two weeks ago but nothing has "
        "arrived on the card yet.",
        "billing",
    ),
    (
        "Quote needed for license renewal",
        "We need a formal quote for renewing twenty licenses before the "
        "end of the quarter.",
        "billing",
    ),
    (
        "Price for adding five seats",
        "How much would it cost to add five more users to our current "
        "plan?",
        "billing",
    ),
    # --- other: everything that does not fit above ---
    (
        "Desk move for the design team",
        "Our team relocates to the fourth floor next week and the six "
        "desks need to be reassigned.",
        "other",
    ),
    (
        "Coffee machine needs service",
        "The coffee machine in the kitchen leaks and the cleaning team "
        "asked us to report it.",
        "other",
    ),
    (
        "Dark mode for the intranet",
        "A dark mode option for the intranet would reduce glare during "
        "the evening shift.",
        "other",
    ),
    (
        "Unsubscribe from the newsletter",
        "Please remove my address from the monthly company newsletter.",
        "other",
    ),
    (
        "Training session on the ticket portal",
        "Could the IT team run a short session on the new ticket portal "
        "for our group?",
        "other",
    ),
    (
        "Where can I find the org chart?",
        "I need the current organizational chart for an internal "
        "presentation tomorrow.",
        "other",
    ),
)
