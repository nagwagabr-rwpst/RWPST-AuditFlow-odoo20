# Part of RWPST AuditFlow. See module manifest for license.

from odoo import _, api, fields, models

# Single-space label: hides auto titling in the form without showing a second caption.
_KPI_NOLABEL = " "


class AuditDashboardKpi(models.TransientModel):
    _name = "audit.dashboard.kpi"
    _description = "Audit Health KPIs (Control Center)"
    _rec_name = "name"

    name = fields.Char(
        string="Title",
        readonly=True,
        default=lambda self: _("Audit Control Center"),
    )
    kpi_total_engagements = fields.Integer(string="Total Audit Operations", readonly=True)
    kpi_not_ready_engagements = fields.Integer(string="Operations Not Report-Ready", readonly=True)
    kpi_report_ready_engagements = fields.Integer(string="Report-Ready Operations", readonly=True)
    kpi_overdue_findings = fields.Integer(string="Delayed Review Results", readonly=True)
    kpi_critical_findings = fields.Integer(string="High Risk Review Results", readonly=True)
    kpi_open_findings = fields.Integer(string="Open Review Results", readonly=True)
    kpi_closed_findings = fields.Integer(string="Closed Review Results", readonly=True)

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        res["name"] = _("Audit Control Center")
        Eng = self.env["audit.engagement"]
        Fin = self.env["audit.finding"]
        values = {
            "kpi_total_engagements": Eng.search_count([]),
            "kpi_not_ready_engagements": Eng.search_count(
                [("is_not_ready", "=", True)]
            ),
            "kpi_report_ready_engagements": Eng.search_count(
                [("report_ready", "=", True)]
            ),
            "kpi_overdue_findings": Fin.search_count(
                [("is_overdue", "=", True)]
            ),
            "kpi_critical_findings": Fin.search_count(
                [("severity", "=", "critical")]
            ),
            "kpi_open_findings": Fin.search_count(
                [("status", "=", "open")]
            ),
            "kpi_closed_findings": Fin.search_count(
                [("status", "=", "closed")]
            ),
        }
        for key, value in values.items():
            if not fields_list or key in fields_list:
                res[key] = value
        return res

    def _action(self, xml_id):
        self.ensure_one()
        return self.env["ir.actions.actions"]._for_xml_id(
            "auditflow_standard.%s" % xml_id
        )

    def action_open_total_engagements(self):
        return self._action("action_audit_engagement")

    def action_open_not_ready_engagements(self):
        return self._action("action_not_ready_engagements")

    def action_open_report_ready_engagements(self):
        return self._action("action_report_ready_engagements")

    def action_open_overdue_findings(self):
        return self._action("action_overdue_findings")

    def action_open_critical_findings(self):
        return self._action("action_critical_findings_kpi")

    def action_open_open_findings(self):
        return self._action("action_open_findings_kpi")

    def action_open_closed_findings(self):
        return self._action("action_closed_findings_kpi")
