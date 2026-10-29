from odoo import _, http
from odoo.exceptions import AccessError, MissingError
from odoo.http import request
from odoo.addons.portal.controllers.portal import CustomerPortal, pager as portal_pager


class SmartAuditPortal(CustomerPortal):
    """Portal surface for Smart Audit.

    Security model:
      * List and detail routes redirect to /my when access is denied or
        the record is missing. The response carries neither the exception
        nor any record data.
      * Plan visibility stays in ir.access. This controller only adds the
        participation domain, so an auditor still sees their own drafts.
      * Detail uses `_document_check_access` for the plan. That helper
        returns a superuser record, so the template receives the caller's
        plan and an indicator recordset searched in the caller's environment.
    """

    # ------------------------------------------------------------------
    # /my home tile integration
    # ------------------------------------------------------------------
    def _prepare_portal_counter_values(self, counter):
        if counter == 'audit_count':
            return 'audit.plan.stable', self._get_audit_plan_domain(), 'read'
        return super()._prepare_portal_counter_values(counter)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _get_audit_plan_domain(self):
        """Domain for the portal list view.

        Role-specific visibility (including draft filtering for auditees)
        is enforced by ir.access, so this domain only expresses the
        "records the current user participates in" intent.
        """
        user = request.env.user
        return [
            '|',
            ('client_id', '=', user.partner_id.id),
            ('lead_auditor_id', '=', user.id),
        ]

    def _portal_plan_indicators(self, plan):
        """Indicators on ``plan`` that the current user may read.

        ``plan`` may be the superuser record returned by
        ``_document_check_access``. Searching here applies ir.access,
        including company restrictions. A user who cannot read the
        indicator model gets an empty set rather than an error page.
        """
        Indicator = request.env['audit.indicator.stable']
        try:
            return Indicator.search([('plan_id', '=', plan.id)])
        except AccessError:
            return Indicator.browse()

    # ------------------------------------------------------------------
    # Routes
    # ------------------------------------------------------------------
    @http.route(
        ['/my/audit', '/my/audit/page/<int:page>'],
        type='http', auth='user', website=True,
    )
    def portal_my_audit(self, page=1, sortby='date', **kw):
        Plan = request.env['audit.plan.stable']
        domain = self._get_audit_plan_domain()

        searchbar_sortings = {
            'date': {'label': _('Newest'), 'order': 'start_date desc, id desc'},
            'name': {'label': _('Reference'), 'order': 'name'},
            'state': {'label': _('Status'), 'order': 'state'},
        }
        # portal.portal_searchbar indexes searchbar_sortings[sortby] directly.
        if sortby not in searchbar_sortings:
            sortby = 'date'
        order = searchbar_sortings[sortby]['order']

        try:
            total = Plan.search_count(domain)
            pager = portal_pager(
                url='/my/audit',
                url_args={'sortby': sortby},
                total=total, page=page, step=20,
            )
            plans = Plan.search(
                domain, order=order, limit=20, offset=pager['offset'],
            )
        except AccessError:
            return request.redirect('/my')
        values = {
            'plans': plans,
            'page_name': 'audit',
            'pager': pager,
            'sortby': sortby,
            'searchbar_sortings': searchbar_sortings,
            'default_url': '/my/audit',
        }
        return request.render(
            'auditflow_standard.portal_my_audit', values,
        )

    @http.route(
        ['/my/audit/plan/<int:plan_id>'],
        type='http', auth='user', website=True,
    )
    def portal_view_plan(self, plan_id, **kw):
        try:
            plan_sudo = self._document_check_access(
                'audit.plan.stable', plan_id,
            )
        except (AccessError, MissingError):
            return request.redirect('/my')
        # Do not render the superuser record. Its indicator_ids read loads
        # every child with sudo(). The template iterates the filtered set.
        plan = request.env['audit.plan.stable'].browse(plan_sudo.id)
        return request.render(
            'auditflow_standard.portal_audit_plan',
            {
                'plan': plan,
                'indicators': self._portal_plan_indicators(plan),
                'page_name': 'audit',
            },
        )
