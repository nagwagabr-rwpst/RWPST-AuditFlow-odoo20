from odoo import _, api, fields, models
from odoo.exceptions import UserError


class AuditEngagement(models.Model):
    _name = 'audit.engagement'
    _description = 'Audit Operation'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'id desc'

    # Reference: sequence codes (ENG/…) stay Latin; demo titles are translated via ar.po.
    # Empty Arabic msgstr for codes falls back to the English source string.
    name = fields.Char(
        string='Reference',
        required=True, copy=False, readonly=True,
        default=lambda self: _('New'),
        tracking=True,
        translate=True,
    )
    auditee_id = fields.Many2one(
        'res.partner', string='Entity Under Review',
        tracking=True, check_company=True,
    )
    auditor_ids = fields.Many2many(
        'res.users', string='Audit Team', tracking=True,
    )
    lead_auditor_id = fields.Many2one(
        'res.users', string='Lead Reviewer', tracking=True,
    )
    scope = fields.Text(string='Scope', tracking=True, translate=True)
    objectives = fields.Text(string='Objectives', tracking=True, translate=True)
    start_date = fields.Date(string='Start Date', tracking=True)
    end_date = fields.Date(string='End Date', tracking=True)
    state = fields.Selection(
        [
            ('draft', 'Draft'),
            ('fieldwork', 'Fieldwork'),
            ('reporting', 'Reporting'),
            ('issued', 'Issued'),
            ('closed', 'Closed'),
            ('cancelled', 'Cancelled'),
        ],
        string='Execution Status',
        default='draft', tracking=True,
    )
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        default=lambda self: self.env.company,
        required=True,
    )
    finding_ids = fields.One2many(
        'audit.finding', 'engagement_id', string='Review Results',
    )
    finding_count = fields.Integer(compute='_compute_finding_count')
    overdue_finding_count = fields.Integer(
        string='Delayed Review Results',
        compute='_compute_finding_urgency_counts',
        store=True,
    )
    due_soon_finding_count = fields.Integer(
        string='Due soon review results',
        compute='_compute_finding_urgency_counts',
        store=True,
    )
    open_finding_count = fields.Integer(
        string='Open Review Results',
        compute='_compute_finding_kpi_counts',
        store=True,
    )
    closed_finding_count = fields.Integer(
        string='Closed Review Results',
        compute='_compute_finding_kpi_counts',
        store=True,
    )
    critical_finding_count = fields.Integer(
        string='High Risk Review Results',
        compute='_compute_finding_kpi_counts',
        store=True,
    )
    report_ready = fields.Boolean(
        string='Report Ready',
        compute='_compute_report_readiness',
        store=True,
    )
    report_readiness_message = fields.Text(
        string='Readiness',
        compute='_compute_report_readiness',
        store=True,
    )
    is_not_ready = fields.Boolean(
        string='Not Ready',
        compute='_compute_is_not_ready',
        store=True,
    )
    readiness_label = fields.Selection(
        [
            ('ready', 'Ready'),
            ('not_ready', 'Not Ready'),
        ],
        string='Readiness (chart)',
        compute='_compute_readiness_label',
        store=True,
    )
    not_ready_flag_count = fields.Integer(
        string='Not Ready (stat)',
        compute='_compute_not_ready_flag_count',
    )
    corrective_action_ids = fields.One2many(
        'audit.corrective.action',
        'engagement_id',
        string='Corrective Actions (CAPA)',
        readonly=True,
    )
    corrective_action_count = fields.Integer(
        string='Total Corrective Actions (CAPA)',
        compute='_compute_corrective_action_rollups',
        store=True,
    )
    open_corrective_action_count = fields.Integer(
        string='Open Corrective Actions (CAPA)',
        compute='_compute_corrective_action_rollups',
        store=True,
    )
    overdue_corrective_action_count = fields.Integer(
        string='Delayed Corrective Actions (CAPA)',
        compute='_compute_corrective_action_rollups',
        store=True,
    )
    completed_corrective_action_count = fields.Integer(
        string='Completed Corrective Actions (CAPA)',
        compute='_compute_corrective_action_rollups',
        store=True,
    )

    @api.depends('report_ready')
    def _compute_is_not_ready(self):
        for eng in self:
            eng.is_not_ready = not eng.report_ready

    @api.depends('is_not_ready')
    def _compute_readiness_label(self):
        for eng in self:
            eng.readiness_label = 'not_ready' if eng.is_not_ready else 'ready'

    @api.depends('is_not_ready')
    def _compute_not_ready_flag_count(self):
        for eng in self:
            eng.not_ready_flag_count = 1 if eng.is_not_ready else 0

    @api.depends(
        'finding_ids',
        'finding_ids.corrective_action_ids',
        'finding_ids.corrective_action_ids.state',
        'finding_ids.corrective_action_ids.is_overdue',
    )
    def _compute_corrective_action_rollups(self):
        done_cancel = frozenset({'done', 'cancelled'})
        for eng in self:
            actions = eng.finding_ids.mapped('corrective_action_ids')
            eng.corrective_action_count = len(actions)
            eng.open_corrective_action_count = len(
                actions.filtered(lambda a: (a.state or '') not in done_cancel)
            )
            eng.overdue_corrective_action_count = len(actions.filtered('is_overdue'))
            eng.completed_corrective_action_count = len(
                actions.filtered(lambda a: (a.state or '') == 'done')
            )

    @api.depends('finding_ids')
    def _compute_finding_count(self):
        for record in self:
            record.finding_count = len(record.finding_ids)

    @api.depends('finding_ids.is_overdue', 'finding_ids.is_due_soon')
    def _compute_finding_urgency_counts(self):
        for eng in self:
            findings = eng.finding_ids
            eng.overdue_finding_count = len(
                findings.filtered('is_overdue')
            )
            eng.due_soon_finding_count = len(
                findings.filtered('is_due_soon')
            )

    @api.depends('finding_ids', 'finding_ids.status', 'finding_ids.severity')
    def _compute_finding_kpi_counts(self):
        closed_states = {'closed', 'done', 'cancelled'}
        open_states = {'open', 'in_review'}
        for eng in self:
            f = eng.finding_ids
            eng.open_finding_count = len(
                f.filtered(lambda r: (r.status or '') in open_states)
            )
            eng.closed_finding_count = len(
                f.filtered(lambda r: (r.status or '') in closed_states)
            )
            eng.critical_finding_count = len(
                f.filtered(lambda r: r.severity == 'critical')
            )

    def _report_readiness_issues(self):
        self.ensure_one()
        issues = []
        if not self.auditee_id:
            issues.append(_('Entity under review is required for report readiness.'))
        if not self.lead_auditor_id:
            issues.append(_('Lead reviewer is required for report readiness.'))
        if not (self.start_date and self.end_date):
            issues.append(_('Start and end dates are required for report readiness.'))
        if not (self.scope and str(self.scope).strip()):
            issues.append(_('Scope is required for report readiness.'))
        if not (self.objectives and str(self.objectives).strip()):
            issues.append(_('Objectives are required for report readiness.'))

        open_states = {'open', 'in_review'}
        for f in self.finding_ids:
            if not f.severity or not f.status:
                issues.append(
                    _('Review result “%s” must include severity and execution status.')
                    % (f.name or f.id)
                )
                continue
            if f.status not in open_states:
                continue
            if not (f.action_plan and str(f.action_plan).strip()):
                issues.append(
                    _('Open review result “%s” must have an action plan.')
                    % (f.name or f.id)
                )
            if not f.target_date:
                issues.append(
                    _('Open review result “%s” must have a target date.')
                    % (f.name or f.id)
                )
            if not f.responsible_id:
                issues.append(
                    _('Open review result “%s” must have a corrective action owner.')
                    % (f.name or f.id)
                )
            if not (f.management_response and str(f.management_response).strip()):
                issues.append(
                    _('Open review result “%s” must have a management response.')
                    % (f.name or f.id)
                )
            if f.severity == 'critical' and not f.corrective_action_ids:
                issues.append(
                    _('High risk review result “%s” must have at least one Corrective Action (CAPA).')
                    % (f.name or f.id)
                )
        if self.overdue_corrective_action_count:
            issues.append(
                _('Delayed Corrective Actions (CAPA) exist; management follow-up is incomplete.')
            )
        return issues

    @api.depends(
        'auditee_id',
        'lead_auditor_id',
        'scope',
        'objectives',
        'start_date',
        'end_date',
        'finding_ids',
        'finding_ids.name',
        'finding_ids.severity',
        'finding_ids.status',
        'finding_ids.action_plan',
        'finding_ids.target_date',
        'finding_ids.responsible_id',
        'finding_ids.management_response',
        'finding_ids.corrective_action_ids',
        'overdue_corrective_action_count',
    )
    def _compute_report_readiness(self):
        for eng in self:
            iss = eng._report_readiness_issues()
            eng.report_readiness_message = '\n'.join(iss) if iss else _(
                'All report readiness checks passed.'
            )
            eng.report_ready = not bool(iss)

    def action_check_report_readiness(self):
        self.ensure_one()
        self._compute_report_readiness()
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Report readiness'),
                'message': self.report_readiness_message,
                'type': 'success' if self.report_ready else 'warning',
                'sticky': not self.report_ready,
            },
        }

    def action_view_findings(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Review Results'),
            'res_model': 'audit.finding',
            'view_mode': 'list,form',
            'search_view_id': self.env.ref(
                'auditflow_standard.view_audit_finding_search'
            ).id,
            'views': [
                (self.env.ref('auditflow_standard.view_audit_finding_list').id, 'list'),
                (self.env.ref('auditflow_standard.view_audit_finding_form').id, 'form'),
            ],
            'domain': [('engagement_id', '=', self.id)],
            'context': {'default_engagement_id': self.id},
        }

    def action_view_overdue_findings(self):
        self.ensure_one()
        action = dict(self.action_view_findings())
        action['name'] = _('Delayed Review Results')
        action['search_view_id'] = self.env.ref(
            'auditflow_standard.view_audit_finding_search'
        ).id
        action['domain'] = [
            ('engagement_id', '=', self.id),
            ('is_overdue', '=', True),
        ]
        context = dict(action.get('context') or {})
        context['default_engagement_id'] = self.id
        context['search_default_filter_overdue'] = 1
        action['context'] = context
        return action

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
            'domain': [('engagement_id', '=', self.id)],
            'context': {},
        }

    def action_view_open_corrective_actions(self):
        self.ensure_one()
        act = self.action_view_corrective_actions()
        act['domain'] = [
            ('engagement_id', '=', self.id),
            ('state', 'not in', ['done', 'cancelled']),
        ]
        return act

    def action_view_overdue_corrective_actions(self):
        self.ensure_one()
        act = self.action_view_corrective_actions()
        act['domain'] = [('engagement_id', '=', self.id), ('is_overdue', '=', True)]
        ctx = dict(act.get('context') or {})
        ctx['search_default_filter_overdue'] = 1
        act['context'] = ctx
        return act

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code(
                    'audit.engagement'
                ) or _('New')
        return super().create(vals_list)

    def action_set_to_draft(self):
        self.write({'state': 'draft'})

    def action_start_fieldwork(self):
        self.write({'state': 'fieldwork'})

    def action_move_to_reporting(self):
        self.write({'state': 'reporting'})

    def action_issue_report(self):
        not_ready = self.filtered(lambda e: not e.report_ready)
        if not_ready:
            if len(self) != 1:
                raise UserError(
                    _(
                        'You can only review report readiness for one audit operation at a time. '
                        'Select a single operation, or ensure all selected operations are ready to issue.'
                    )
                )
            engagement = self
            return {
                'type': 'ir.actions.act_window',
                'name': _('Issue Report Warning'),
                'res_model': 'audit.engagement.issue.warning.wizard',
                'view_mode': 'form',
                'target': 'new',
                'context': {
                    'default_engagement_id': engagement.id,
                    'default_message': engagement.report_readiness_message or '',
                },
            }
        return self.write({'state': 'issued'})

    def action_close(self):
        self.write({'state': 'closed'})

    def action_cancel(self):
        self.write({'state': 'cancelled'})
