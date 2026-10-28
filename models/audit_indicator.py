from odoo import api, fields, models


class AuditIndicator(models.Model):
    _name = 'audit.indicator.stable'
    _description = 'Audit Indicator / KRI'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'plan_id, name'
    _check_company_auto = True

    name = fields.Char(
        string='Indicator', required=True, tracking=True, translate=True,
    )
    category = fields.Selection(
        [
            ('control_design', 'Control Design'),
            ('control_operational', 'Control Operational'),
            ('compliance', 'Compliance'),
            ('risk', 'Risk'),
        ],
        string='Category', default='control_operational', tracking=True, index=True,
    )
    description = fields.Html(string='Description', translate=True)
    baseline = fields.Float(string='Baseline', tracking=True)
    target = fields.Float(string='Target', tracking=True)
    current_value = fields.Float(string='Current Value', tracking=True)
    score = fields.Float(
        string='Score (%)', compute='_compute_score', store=True,
        help="Capped at 100%. Computed as current_value / target * 100.",
    )
    plan_id = fields.Many2one(
        'audit.plan.stable', string='Plan', ondelete='cascade',
        index=True, check_company=True,
    )
    company_id = fields.Many2one(
        'res.company', string='Company',
        compute='_compute_company_id', store=True, index=True, readonly=True,
    )

    @api.depends('current_value', 'target')
    def _compute_score(self):
        for rec in self:
            if rec.target:
                rec.score = min(100.0, rec.current_value / rec.target * 100.0)
            else:
                rec.score = 0.0

    @api.depends('plan_id.company_id')
    def _compute_company_id(self):
        default_company = self.env.company
        for rec in self:
            rec.company_id = rec.plan_id.company_id or default_company
