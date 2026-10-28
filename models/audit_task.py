from odoo import api, fields, models


class AuditTask(models.Model):
    _name = 'audit.task.stable'
    _description = 'Audit Task / Procedure'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'sequence, due_date, id'
    _check_company_auto = True

    sequence = fields.Integer(default=10)
    active = fields.Boolean(string='Active', default=True)
    name = fields.Char(
        string='Task', required=True, tracking=True, translate=True,
    )
    plan_id = fields.Many2one(
        'audit.plan.stable', string='Plan', ondelete='cascade',
        index=True, check_company=True,
    )
    assigned_to = fields.Many2one(
        'res.users', string='Assigned To', tracking=True,
        check_company=True, domain="[('share', '=', False)]",
    )
    status = fields.Selection(
        [
            ('pending', 'Pending'),
            ('in_progress', 'In Progress'),
            ('done', 'Done'),
        ],
        string='Status', default='pending', tracking=True, index=True, copy=False,
    )
    due_date = fields.Date(string='Due Date', tracking=True)
    note = fields.Html(string='Note', translate=True)
    company_id = fields.Many2one(
        'res.company', string='Company',
        compute='_compute_company_id', store=True, index=True, readonly=True,
    )

    @api.depends('plan_id.company_id')
    def _compute_company_id(self):
        default_company = self.env.company
        for rec in self:
            rec.company_id = rec.plan_id.company_id or default_company

    def action_start(self):
        self.write({'status': 'in_progress'})

    def action_done(self):
        self.write({'status': 'done'})
