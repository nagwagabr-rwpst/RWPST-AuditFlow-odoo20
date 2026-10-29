from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

_CONFIG_PARAM_DUE_SOON_DAYS = 'fine_tech_smart_audit.due_soon_days'
_DEFAULT_DUE_SOON_DAYS = 7
# Not open / in-review: do not show overdue or due soon (include legacy "closed")
_FINDING_STATUS_TERMINAL = frozenset({'closed', 'done', 'cancelled'})
_CAPA_DONE_STATES = frozenset({'done', 'cancelled'})
# (impact, likelihood) -> inherent risk rating (3x3 matrix)
_RISK_RATING_MATRIX = {
    ('low', 'low'): 'low',
    ('low', 'medium'): 'low',
    ('low', 'high'): 'medium',
    ('medium', 'low'): 'low',
    ('medium', 'medium'): 'medium',
    ('medium', 'high'): 'high',
    ('high', 'low'): 'medium',
    ('high', 'medium'): 'high',
    ('high', 'high'): 'critical',
}


class AuditFinding(models.Model):
    _name = 'audit.finding'
    _description = 'Audit review result'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'id desc'

    name = fields.Char(
        string='Review Result', required=True, tracking=True, translate=True
    )
    engagement_id = fields.Many2one(
        'audit.engagement',
        string='Audit Operation',
        required=True,
        ondelete='cascade',
        tracking=True,
    )
    description = fields.Text(string='Description', tracking=True, translate=True)
    severity = fields.Selection(
        [
            ('low', 'Low'),
            ('medium', 'Medium'),
            ('high', 'High'),
            ('critical', 'High Risk'),
        ],
        string='Severity',
        default='medium', required=True, tracking=True,
    )
    status = fields.Selection(
        [
            ('open', 'Open'),
            ('in_review', 'In Review'),
            ('closed', 'Closed'),
            ('done', 'Completed'),
            ('cancelled', 'Cancelled'),
        ],
        string='Execution Status',
        default='open', required=True, tracking=True,
    )
    root_cause = fields.Text(
        string='Root Cause', tracking=True, translate=True
    )
    impact = fields.Text(
        string='Business Impact (narrative)', tracking=True, translate=True
    )
    recommendation = fields.Text(
        string='Recommendation', tracking=True, translate=True
    )
    owner_id = fields.Many2one('res.users', string='Accountable Owner', tracking=True)
    due_date = fields.Date(string='Target Execution Date', tracking=True)
    attachment_ids = fields.Many2many(
        'ir.attachment',
        'audit_finding_ir_attachments_rel',
        'finding_id',
        'attachment_id',
        string='Attachments',
    )
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        compute='_compute_company_id',
        store=True,
    )
    color = fields.Integer(compute='_compute_color', store=True)
    is_overdue = fields.Boolean(
        string='Delayed',
        compute='_compute_due_traffic_lights',
        store=True,
        index=True,
    )
    is_due_soon = fields.Boolean(
        string='Is Due Soon',
        compute='_compute_due_traffic_lights',
        store=True,
        index=True,
    )
    action_plan = fields.Text(
        string='Action Plan', tracking=True, translate=True
    )
    target_date = fields.Date(string='Action Target Date', tracking=True)
    responsible_id = fields.Many2one(
        'res.users',
        string='Corrective Action Owner',
        tracking=True,
        help='Owner of the corrective / action plan.',
    )
    management_response = fields.Text(
        string='Management Response', tracking=True, translate=True
    )
    risk_impact = fields.Selection(
        [
            ('low', 'Low'),
            ('medium', 'Medium'),
            ('high', 'High'),
        ],
        string='Impact (risk)',
        tracking=True,
    )
    risk_likelihood = fields.Selection(
        [
            ('low', 'Low'),
            ('medium', 'Medium'),
            ('high', 'High'),
        ],
        string='Likelihood',
        tracking=True,
    )
    risk_rating = fields.Selection(
        [
            ('low', 'Low'),
            ('medium', 'Medium'),
            ('high', 'High'),
            ('critical', 'High Risk'),
        ],
        string='Risk Rating',
        compute='_compute_risk_rating',
        store=True,
        index=True,
    )
    corrective_action_ids = fields.One2many(
        'audit.corrective.action',
        'finding_id',
        string='Corrective Actions (CAPA)',
    )
    corrective_action_count = fields.Integer(
        string='Corrective Actions (CAPA) count',
        compute='_compute_corrective_action_stats',
        store=True,
        compute_sudo=True,
    )
    open_action_count = fields.Integer(
        string='Open Corrective Actions (CAPA)',
        compute='_compute_corrective_action_stats',
        store=True,
        compute_sudo=True,
    )
    overdue_action_count = fields.Integer(
        string='Delayed corrective actions',
        compute='_compute_corrective_action_stats',
        store=True,
        compute_sudo=True,
    )
    corrective_status = fields.Selection(
        [
            ('no_action', 'No action'),
            ('pending', 'Pending action'),
            ('overdue', 'Delayed'),
            ('completed', 'Completed'),
        ],
        string='Corrective follow-up',
        compute='_compute_corrective_action_stats',
        store=True,
        compute_sudo=True,
    )

    _SEVERITY_COLOR_MAP = {
        'low': 10,
        'medium': 3,
        'high': 2,
        'critical': 1,
    }

    @api.depends('engagement_id.company_id')
    def _compute_company_id(self):
        for record in self:
            record.company_id = record.engagement_id.company_id

    @api.depends('severity')
    def _compute_color(self):
        for record in self:
            record.color = self._SEVERITY_COLOR_MAP.get(record.severity, 0)

    @api.depends(
        'corrective_action_ids',
        'corrective_action_ids.state',
        'corrective_action_ids.is_overdue',
    )
    def _compute_corrective_action_stats(self):
        for rec in self:
            actions = rec.corrective_action_ids
            rec.corrective_action_count = len(actions)
            rec.open_action_count = len(
                actions.filtered(lambda a: (a.state or '') not in _CAPA_DONE_STATES)
            )
            ovd = actions.filtered('is_overdue')
            rec.overdue_action_count = len(ovd)
            if not actions:
                rec.corrective_status = 'no_action'
            elif ovd:
                rec.corrective_status = 'overdue'
            elif all((a.state or '') in _CAPA_DONE_STATES for a in actions):
                rec.corrective_status = 'completed'
            else:
                rec.corrective_status = 'pending'

    @api.depends('risk_impact', 'risk_likelihood')
    def _compute_risk_rating(self):
        for rec in self:
            ri, rl = rec.risk_impact, rec.risk_likelihood
            if not ri or not rl:
                rec.risk_rating = False
            else:
                rec.risk_rating = _RISK_RATING_MATRIX.get((ri, rl), 'medium')

    @api.onchange('severity')
    def _onchange_severity_default_risk_impact(self):
        """Non-destructive hint: suggest risk impact from severity if empty."""
        if self.risk_impact:
            return
        hint = {
            'low': 'low',
            'medium': 'medium',
            'high': 'high',
            'critical': 'high',
        }.get(self.severity)
        if hint:
            self.risk_impact = hint

    @api.model
    def _get_due_soon_days(self):
        """Config window length in days. Invalid ICP value falls back to 7.

        A value of 0 still bounds due-soon to today (see compute).
        """
        value = (
            self.env['ir.config_parameter']
            .sudo()
            .get_str(_CONFIG_PARAM_DUE_SOON_DAYS, str(_DEFAULT_DUE_SOON_DAYS))
        )
        try:
            return max(int(value), 0)
        except (TypeError, ValueError):
            return 7

    @api.depends('due_date', 'status')
    def _compute_due_traffic_lights(self):
        today = fields.Date.context_today(self)
        due_soon_days = self._get_due_soon_days()
        end = fields.Date.add(today, days=due_soon_days)
        for rec in self:
            is_terminal = bool(
                rec.status and rec.status in _FINDING_STATUS_TERMINAL
            )
            due = rec.due_date
            if is_terminal or not due:
                rec.is_overdue = False
                rec.is_due_soon = False
                continue
            is_over = due < today
            if is_over:
                rec.is_overdue = True
                rec.is_due_soon = False
                continue
            rec.is_overdue = False
            rec.is_due_soon = bool(today <= due <= end)

    @api.constrains('severity', 'due_date')
    def _check_critical_due_date(self):
        for record in self:
            if record.severity == 'critical' and not record.due_date:
                raise ValidationError(
                    _('High risk review results must have a target execution date.')
                )

    @api.constrains('severity', 'owner_id')
    def _check_critical_owner(self):
        for record in self:
            if record.severity == 'critical' and not record.owner_id:
                raise ValidationError(
                    _('High risk review results must have an accountable owner.')
                )

    def action_view_corrective_actions(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Corrective Actions (CAPA)'),
            'res_model': 'audit.corrective.action',
            'view_mode': 'list,form',
            'search_view_id': self.env.ref(
                'auditflow_standard.view_audit_corrective_action_search'
            ).id,
            'views': [
                (
                    self.env.ref(
                        'auditflow_standard.view_audit_corrective_action_list'
                    ).id,
                    'list',
                ),
                (
                    self.env.ref(
                        'auditflow_standard.view_audit_corrective_action_form'
                    ).id,
                    'form',
                ),
            ],
            'domain': [('finding_id', '=', self.id)],
            'context': {
                'default_finding_id': self.id,
            },
        }

    def action_view_overdue_corrective_actions(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Delayed corrective actions'),
            'res_model': 'audit.corrective.action',
            'view_mode': 'list,form',
            'search_view_id': self.env.ref(
                'auditflow_standard.view_audit_corrective_action_search'
            ).id,
            'views': [
                (
                    self.env.ref(
                        'auditflow_standard.view_audit_corrective_action_list'
                    ).id,
                    'list',
                ),
                (
                    self.env.ref(
                        'auditflow_standard.view_audit_corrective_action_form'
                    ).id,
                    'form',
                ),
            ],
            'domain': [('finding_id', '=', self.id), ('is_overdue', '=', True)],
            'context': {
                'default_finding_id': self.id,
                'search_default_filter_overdue': 1,
            },
        }
