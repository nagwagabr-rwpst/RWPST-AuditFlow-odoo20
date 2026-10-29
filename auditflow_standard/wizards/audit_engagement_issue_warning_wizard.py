# Part of RWPST AuditFlow. See module manifest for license.

from odoo import fields, models


class AuditEngagementIssueWarningWizard(models.TransientModel):
    _name = "audit.engagement.issue.warning.wizard"
    _description = "Audit Operation Issue Warning Wizard"

    engagement_id = fields.Many2one(
        "audit.engagement",
        string="Audit operation",
        required=True,
        ondelete="cascade",
        check_company=True,
    )
    company_id = fields.Many2one(
    "res.company",
    default=lambda self: self.env.company,
    readonly=True,)

    
    message = fields.Text(readonly=True)

    def action_force_issue(self):
        self.ensure_one()
        self.engagement_id.write({"state": "issued"})
        return {"type": "ir.actions.act_window_close"}
