from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class AuditPlan(models.Model):
    _name = 'audit.plan.stable'
    _description = 'Audit Plan'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'start_date desc, id desc'
    _check_company_auto = True

    name = fields.Char(
        string='Reference',
        required=True,
        copy=False,
        tracking=True,
        default=lambda self: _('New'),
        help="Auto-generated via sequence when left blank.",
    )
    client_id = fields.Many2one(
        'res.partner',
        string='Entity Under Review',
        tracking=True,
        check_company=True,
        index=True,
    )
    lead_auditor_id = fields.Many2one(
        'res.users',
        string='Lead Reviewer',
        tracking=True,
        check_company=True,
        index=True,
        default=lambda self: self.env.user,
        domain="[('share', '=', False)]",
    )
    description = fields.Html(
        string='Scope & Objectives',
        translate=True,
    )
    start_date = fields.Date(string='Start Date', tracking=True)
    end_date = fields.Date(string='End Date', tracking=True)
    state = fields.Selection(
        [
            ('draft', 'Draft'),
            ('open', 'In Progress'),
            ('done', 'Done'),
            ('cancel', 'Cancelled'),
        ],
        string='Status',
        default='draft',
        tracking=True,
        index=True,
        copy=False,
    )
    color = fields.Integer(string='Color Index', default=0)
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        required=True,
        index=True,
        default=lambda self: self.env.company,
    )

    task_ids = fields.One2many(
        'audit.task.stable',
        'plan_id',
        string='Tasks',
    )
    indicator_ids = fields.One2many(
        'audit.indicator.stable',
        'plan_id',
        string='Indicators',
    )

    task_count = fields.Integer(compute='_compute_task_count')
    progress = fields.Float(
        string='Progress (%)',
        compute='_compute_progress',
        store=True,
        help="Percentage of tasks in 'Done' state.",
    )

    _name_company_uniq = models.Constraint(
        'UNIQUE(name, company_id)',
        'Audit Plan reference must be unique per company.',
    )

    # ------------------------------------------------------------------
    # Computes
    # ------------------------------------------------------------------
    @api.depends('task_ids.status')
    def _compute_progress(self):
        for rec in self:
            total = len(rec.task_ids)
            done = sum(1 for task in rec.task_ids if task.status == 'done')
            rec.progress = (done / total * 100.0) if total else 0.0

    @api.depends('task_ids')
    def _compute_task_count(self):
        for rec in self:
            rec.task_count = len(rec.task_ids)

    # ------------------------------------------------------------------
    # Constraints
    # ------------------------------------------------------------------
    @api.constrains('start_date', 'end_date')
    def _check_dates(self):
        for rec in self:
            if rec.start_date and rec.end_date and rec.end_date < rec.start_date:
                raise ValidationError(_("End Date cannot be before Start Date."))

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                company_id = vals.get('company_id') or self.env.company.id
                vals['name'] = (
                    self.env['ir.sequence']
                    .with_company(company_id)
                    .next_by_code('audit.plan.stable')
                    or _('New')
                )
        return super().create(vals_list)

    # ------------------------------------------------------------------
    # Workflow actions
    # ------------------------------------------------------------------
    def action_set_draft(self):
        self.write({'state': 'draft'})

    def action_open(self):
        self.write({'state': 'open'})

    def action_done(self):
        self.write({'state': 'done'})

    def action_cancel(self):
        self.write({'state': 'cancel'})

    def action_view_tasks(self):
        self.ensure_one()
        return {
            'name': _('Tasks'),
            'type': 'ir.actions.act_window',
            'res_model': 'audit.task.stable',
            'view_mode': 'list,form',
            'domain': [('plan_id', '=', self.id)],
            'context': {'default_plan_id': self.id},
        }