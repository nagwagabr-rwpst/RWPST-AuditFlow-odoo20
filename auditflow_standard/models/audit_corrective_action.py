# -*- coding: utf-8 -*-

from odoo import _, api, fields, models
from odoo.exceptions import AccessError

_CAPA_DONE_STATES = frozenset({'done', 'cancelled'})


class AuditCorrectiveAction(models.Model):
    _name = 'audit.corrective.action'
    _description = 'الإجراء التصحيحي'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'target_date asc, id desc'

    name = fields.Char(
        string='عنوان الإجراء التصحيحي',
        required=True,
        tracking=True,
        translate=True,
    )
    finding_id = fields.Many2one(
        'audit.finding',
        string='نتيجة المراجعة',
        required=True,
        ondelete='cascade',
        tracking=True,
    )
    engagement_id = fields.Many2one(
        'audit.engagement',
        string='عملية المراجعة',
        related='finding_id.engagement_id',
        store=True,
        readonly=True,
        index=True,
    )
    company_id = fields.Many2one(
        'res.company',
        string='الشركة',
        related='engagement_id.company_id',
        store=True,
        readonly=True,
    )
    description = fields.Text(string='وصف الإجراء', tracking=True, translate=True)
    action_owner_id = fields.Many2one(
        'res.users',
        string='مالك الإجراء التصحيحي',
        required=True,
        tracking=True,
    )
    target_date = fields.Date(
        string='تاريخ التنفيذ المستهدف', required=True, tracking=True
    )
    completion_date = fields.Date(string='تاريخ الإكمال', tracking=True)
    state = fields.Selection(
        [
            ('draft', 'مسودة'),
            ('assigned', 'مُعيّن'),
            ('in_progress', 'قيد التنفيذ'),
            ('done', 'مكتمل'),
            ('cancelled', 'ملغي'),
        ],
        string='حالة التنفيذ',
        default='draft',
        required=True,
        tracking=True,
    )
    is_overdue = fields.Boolean(
        string='متأخر التنفيذ',
        compute='_compute_overdue_metrics',
        store=True,
        index=True,
    )
    days_overdue = fields.Integer(
        string='أيام التأخير',
        compute='_compute_overdue_metrics',
        store=True,
    )
    priority = fields.Selection(
        [
            ('low', 'منخفض'),
            ('medium', 'متوسط'),
            ('high', 'مرتفع'),
            ('critical', 'عالي الخطورة'),
        ],
        string='الأولوية',
        default='medium',
        required=True,
        tracking=True,
    )
    evidence_attachment_ids = fields.Many2many(
        'ir.attachment',
        'audit_corrective_action_ir_attachment_rel',
        'corrective_action_id',
        'attachment_id',
        string='الأدلة والمرفقات',
    )
    management_comment = fields.Text(
        string='رد الإدارة', tracking=True, translate=True
    )
    followup_notes = fields.Text(
        string='ملاحظات المتابعة', tracking=True, translate=True
    )

    @api.depends('target_date', 'state')
    def _compute_overdue_metrics(self):
        today = fields.Date.context_today(self)
        for rec in self:
            td = rec.target_date
            if (
                td
                and td < today
                and (rec.state or '') not in _CAPA_DONE_STATES
            ):
                rec.is_overdue = True
                rec.days_overdue = (today - td).days
            else:
                rec.is_overdue = False
                rec.days_overdue = 0

    def action_assign(self):
        self.filtered(lambda r: r.state == 'draft').write({'state': 'assigned'})

    def action_start(self):
        self.filtered(
            lambda r: r.state in ('draft', 'assigned')
        ).write({'state': 'in_progress'})

    def action_done(self):
        today = fields.Date.context_today(self)
        self.filtered(
            lambda r: r.state not in _CAPA_DONE_STATES
        ).write({
            'state': 'done',
            'completion_date': today,
        })

    def action_cancel(self):
        self.filtered(
            lambda r: r.state not in _CAPA_DONE_STATES
        ).write({'state': 'cancelled'})

    def action_reset_draft(self):
        self.write({'state': 'draft', 'completion_date': False})

    def unlink(self):
        if not self.env.user.has_group(
            'auditflow_standard.group_audit_manager'
        ) and not self.env.user.has_group(
            'auditflow_standard.group_audit_cae'
        ):
            if any(rec.state == 'done' for rec in self):
                raise AccessError(
                    _('لا يمكن للمراجعين حذف الإجراءات التصحيحية (CAPA) المكتملة.')
                )
        return super().unlink()
