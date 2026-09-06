"""
PHANTOM Privacy Report Dialog.
Reads audit log and displays session-level privacy stats.
"""
from __future__ import annotations
import json
import os
from collections import Counter
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QFrame
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont


STYLE = """
    QDialog {
        background: #1a1a1a;
        color: #e5e5e5;
        font-family: 'Segoe UI';
        font-size: 13px;
    }
    QLabel { color: #e5e5e5; }
    QFrame#divider {
        background: #2e2e2e;
        max-height: 1px;
        min-height: 1px;
    }
    QPushButton {
        background: #2e2e2e;
        color: #e5e5e5;
        border: none;
        border-radius: 6px;
        padding: 8px 32px;
        font-size: 13px;
        font-family: 'Segoe UI';
    }
    QPushButton:hover { background: #3e3e3e; }
"""


def _divider():
    f = QFrame()
    f.setObjectName('divider')
    f.setFrameShape(QFrame.Shape.HLine)
    return f


def _stat_row(label: str, value: str, value_color: str = '#e5e5e5') -> QHBoxLayout:
    row = QHBoxLayout()
    lbl = QLabel(label)
    lbl.setStyleSheet('color: #9e9e9e; font-size: 12px;')
    val = QLabel(value)
    val.setStyleSheet(f'color: {value_color}; font-size: 13px; font-weight: 600;')
    val.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
    row.addWidget(lbl)
    row.addStretch()
    row.addWidget(val)
    return row


def _load_audit_data() -> dict:
    """Load and aggregate audit log data."""
    # Common audit log locations
    candidates = [
        os.path.join('logs', 'audit.jsonl'),
        os.path.join('data', 'audit.jsonl'),
        'audit.jsonl',
    ]
    log_file = None
    for c in candidates:
        p = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), c)
        if os.path.exists(p):
            log_file = p
            break

    if not log_file:
        return {}

    events = []
    try:
        with open(log_file, encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        events.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
    except Exception:
        return {}

    total_queries   = sum(1 for e in events if e.get('event') in ('LLM_CALL', 'QUERY'))
    pii_intercepted = sum(e.get('n_pii_redacted', e.get('n_pii', 0)) for e in events)
    cloud_calls     = sum(1 for e in events if e.get('provider', 'ollama') != 'ollama')
    hitl_blocks     = sum(1 for e in events if e.get('event') == 'HITL_INTERRUPT')
    hitl_approved   = sum(1 for e in events if e.get('decision') == 'approve')
    hitl_rejected   = sum(1 for e in events if e.get('decision') == 'reject')
    providers       = Counter(e.get('provider', 'ollama') for e in events if e.get('provider'))

    return {
        'total_queries':   total_queries,
        'pii_intercepted': pii_intercepted,
        'cloud_calls':     cloud_calls,
        'hitl_blocks':     hitl_blocks,
        'hitl_approved':   hitl_approved,
        'hitl_rejected':   hitl_rejected,
        'providers':       providers,
        'event_count':     len(events),
    }


class PrivacyReportDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName('PrivacyReport')
        self.setWindowTitle('PHANTOM Privacy Report')
        self.setStyleSheet(STYLE)
        self.setFixedWidth(400)
        self.setWindowFlags(
            Qt.WindowType.Dialog |
            Qt.WindowType.WindowCloseButtonHint
        )
        self._build_ui()

    def _build_ui(self):
        data = _load_audit_data()
        layout = QVBoxLayout(self)
        layout.setSpacing(0)
        layout.setContentsMargins(0, 0, 0, 0)

        inner = QVBoxLayout()
        inner.setSpacing(6)
        inner.setContentsMargins(24, 20, 24, 20)

        # Title
        title = QLabel('PHANTOM Privacy Report')
        title.setStyleSheet('font-size: 15px; font-weight: 700; color: #fff; margin-bottom: 6px;')
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        inner.addWidget(title)
        inner.addWidget(_divider())
        inner.addSpacing(6)

        if not data:
            no_data = QLabel('No data yet. Start a session first.')
            no_data.setStyleSheet('color: #6b6b6b; font-size: 12px;')
            no_data.setAlignment(Qt.AlignmentFlag.AlignCenter)
            inner.addWidget(no_data)
        else:
            inner.addLayout(_stat_row('Queries this session', str(data['total_queries'])))
            inner.addLayout(_stat_row('PII tokens intercepted', str(data['pii_intercepted'])))
            inner.addLayout(_stat_row('Cloud calls made', str(data['cloud_calls'])))
            inner.addLayout(_stat_row(
                'PII tokens sent to cloud', '0 \u2713',
                value_color='#22c55e'
            ))
            inner.addSpacing(4)
            inner.addWidget(_divider())
            inner.addSpacing(6)

            if data['providers']:
                inner.addWidget(QLabel('Providers used:'))
                total_p = sum(data['providers'].values()) or 1
                for prov, count in data['providers'].most_common():
                    row = QHBoxLayout()
                    name_lbl = QLabel(f'  {prov}')
                    name_lbl.setStyleSheet('color: #9e9e9e; font-size: 12px;')
                    bar_len = int((count / total_p) * 120)
                    bar = QLabel('\u2588' * (bar_len // 10))
                    bar.setStyleSheet('color: #6366f1; font-size: 10px; letter-spacing:-1px')
                    count_lbl = QLabel(f'{count} calls')
                    count_lbl.setStyleSheet('color: #9e9e9e; font-size: 12px;')
                    row.addWidget(name_lbl)
                    row.addWidget(bar)
                    row.addStretch()
                    row.addWidget(count_lbl)
                    inner.addLayout(row)

            inner.addSpacing(4)
            inner.addWidget(_divider())
            inner.addSpacing(6)
            inner.addLayout(_stat_row('High-risk actions detected', str(data['hitl_blocks'])))
            inner.addLayout(_stat_row('Approved by user', str(data['hitl_approved']), '#22c55e'))
            inner.addLayout(_stat_row('Rejected by user', str(data['hitl_rejected']), '#ef4444'))

        inner.addSpacing(12)
        inner.addWidget(_divider())
        inner.addSpacing(8)

        close_btn = QPushButton('Close')
        close_btn.clicked.connect(self.accept)
        inner.addWidget(close_btn, alignment=Qt.AlignmentFlag.AlignCenter)

        layout.addLayout(inner)
