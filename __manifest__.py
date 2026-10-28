{
    'name': 'RWPST AuditFlow Standard',
    'version': '20.0.4.1.0',
    'summary': (
        'Version 1 Standard: internal audit operations, findings, report readiness, '
        'overdue visibility, executive dashboard — English and Arabic.'
    ),
    'description': """
RWPST AuditFlow — Internal Audit (Version 1 Standard)
======================================================

**Features**

* **Audit operations** — Lifecycle from draft through fieldwork and reporting to issued/closed.
* **Findings** — Severity, status, owners, due dates, overdue and due-soon visibility.
* **Report readiness** — Guided warning when criteria to issue are not met.
* **Executive dashboard** — OWL KPI cards and filtered charts (bar, trend, distribution).
* **Portal** — Basic portal hooks for auditees and mail integration.
* **Bilingual** — English source strings with Arabic translation (backend and web client).

**Scope**

Internal audit management for Odoo focused on audit operations, findings, action and
report readiness, overdue visibility, and dashboards. **Not** a full certified GRC suite.

**Technical**

* Odoo 20 • LGPL-3 • OWL dashboard • Dashboard service API

See ``static/description/index.html`` for listing screenshots and overview.
""",
    'category': 'Services/Audit',
    'author': 'rwpst',
    'website': 'https://nagwagabr-rwpst.github.io/auditflow-landing/',
    'license': 'LGPL-3',
    'price': 59.00,
    'currency': 'USD',
    'depends': ['base', 'mail', 'portal', 'web', 'hr'],
    'data': [
        'security/audit_security.xml',
        'security/ir.access.csv',
        'views/audit_dashboard_actions.xml',
        'data/ir_sequence_data.xml',
        'data/audit_config_parameter_data.xml',
        'views/audit_plan_views.xml',
        'views/audit_task_views.xml',
        'views/audit_indicator_views.xml',
        'views/dashboard_views.xml',
        'views/audit_corrective_action_views.xml',
        'views/menu_views.xml',
        'views/audit_finding_views.xml',
        'views/audit_engagement_views.xml',
        'views/audit_engagement_issue_warning_wizard_views.xml',
        'views/audit_engagement_dashboard_views.xml',
        'views/audit_dashboard_kpi_views.xml',
        'views/audit_dashboard_views.xml',
        'data/audit_dashboard_menu_upgrade.xml',
        'report/audit_engagement_report.xml',
        'report/audit_engagement_report_templates.xml',
        'views/portal_templates.xml',
    ],
    'demo': [
        'demo/audit_demo_data.xml',
        'demo/demo_internal_audit.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'auditflow_standard/static/src/xml/audit_dashboard.xml',
            'auditflow_standard/static/src/js/audit_dashboard.js',
            'auditflow_standard/static/src/css/dashboard.css',
            'auditflow_standard/static/src/scss/audit_dashboard.scss',
            'auditflow_standard/static/src/scss/auditflow_ui.scss',
        ],
        'web.assets_frontend': [
            'auditflow_standard/static/src/scss/auditflow_portal.scss',
        ],
        'web.report_assets_common': [
            'auditflow_standard/static/src/scss/auditflow_report.scss',
        ],
    },
    'images': [
        'static/description/banner.png',
        'static/description/screenshot_dashboard.png',
        'static/description/screenshot_engagement.png',
        'static/description/screenshot_findings.png',
        'static/description/screenshot_warning_wizard.png',
    ],
    'installable': True,
    'application': True,
    'auto_install': False,
}
