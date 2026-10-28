from odoo import api, fields, models


class AuditDashboard(models.TransientModel):
    _name = 'audit.dashboard.stable'
    _description = 'Audit Dashboard'

    total_plans = fields.Integer(string='Total Plans')
    open_plans = fields.Integer(string='Open Plans')
    done_plans = fields.Integer(string='Done Plans')
    total_tasks = fields.Integer(string='Total Tasks')
    open_tasks = fields.Integer(string='Open Tasks')
    overdue_tasks = fields.Integer(string='Overdue Tasks')
    avg_score = fields.Float(string='Average Indicator Score (%)')

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        Plan = self.env['audit.plan.stable']
        Task = self.env['audit.task.stable']
        Ind = self.env['audit.indicator.stable']
        today = fields.Date.context_today(self)

        if 'total_plans' in fields_list:
            res['total_plans'] = Plan.search_count([])
        if 'open_plans' in fields_list:
            res['open_plans'] = Plan.search_count([('state', '=', 'open')])
        if 'done_plans' in fields_list:
            res['done_plans'] = Plan.search_count([('state', '=', 'done')])
        if 'total_tasks' in fields_list:
            res['total_tasks'] = Task.search_count([])
        if 'open_tasks' in fields_list:
            res['open_tasks'] = Task.search_count([('status', '!=', 'done')])
        if 'overdue_tasks' in fields_list:
            res['overdue_tasks'] = Task.search_count([
                ('status', '!=', 'done'),
                ('due_date', '!=', False),
                ('due_date', '<', today),
            ])
        if 'avg_score' in fields_list:
            # Single-SQL aggregate via Odoo 19 _read_group API.
            # Returns a list of tuples shaped by (groupby + aggregates);
            # with no groupby we get [(avg_value,)] or [] on empty sets.
            result = Ind._read_group(
                domain=[],
                groupby=[],
                aggregates=['score:avg'],
            )
            avg = result[0][0] if result and result[0][0] is not None else 0.0
            res['avg_score'] = avg
        return res
