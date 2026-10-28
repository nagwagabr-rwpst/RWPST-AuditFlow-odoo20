# Part of RWPST AuditFlow. See module manifest for license.

import uuid
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch

from odoo import fields
from odoo.exceptions import AccessError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged("post_install", "-at_install", "auditflow")
class TestAuditflowSecurity(TransactionCase):
    def setUp(self):
        super().setUp()
        self.Engagement = self.env["audit.engagement"]
        self.Finding = self.env["audit.finding"]
        self.company = self.env.company
        self.auditee_partner = self.env["res.partner"].create(
            {"name": "Sec test auditee co", "company_id": self.company.id}
        )

    def _login(self):
        return "u_%s" % uuid.uuid4().hex[:12]

    def _engagement_vals_for_users(self, lead, auditors, auditee):
        today = fields.Date.context_today(self.env.user)
        return {
            "auditee_id": auditee.id,
            "lead_auditor_id": lead.id,
            "auditor_ids": [(6, 0, auditors.ids)],
            "start_date": today,
            "end_date": today + timedelta(days=30),
            "scope": "S",
            "objectives": "O",
        }

    def test_internal_user_without_audit_groups_cannot_access_engagement(self):
        """Internal users must belong to an Internal Audit group to use engagement/finding."""
        user = self.env["res.users"].with_context(no_reset_password=True).create(
            {
                "name": "Plain internal",
                "login": self._login(),
                "password": "plain",
                "group_ids": [(6, 0, [self.env.ref("base.group_user").id])],
            }
        )
        with self.assertRaises(AccessError):
            self.Engagement.browse().with_user(user).check_access("read")
        with self.assertRaises(AccessError):
            self.Finding.browse().with_user(user).check_access("read")

    def test_auditor_sees_only_assigned_engagements_and_findings(self):
        g_aud = self.env.ref("auditflow_standard.group_audit_auditor")
        g_user = self.env.ref("base.group_user")
        u_a = self.env["res.users"].with_context(no_reset_password=True).create(
            {
                "name": "Auditor A",
                "login": self._login(),
                "password": "a",
                "group_ids": [(6, 0, [g_user.id, g_aud.id])],
            }
        )
        u_b = self.env["res.users"].with_context(no_reset_password=True).create(
            {
                "name": "Auditor B",
                "login": self._login(),
                "password": "b",
                "group_ids": [(6, 0, [g_user.id, g_aud.id])],
            }
        )
        p_other = self.env["res.partner"].create(
            {"name": "Other auditee", "company_id": self.company.id}
        )
        e_a = self.Engagement.sudo().create(
            self._engagement_vals_for_users(u_a, u_a, self.auditee_partner)
        )
        e_b = self.Engagement.sudo().create(
            self._engagement_vals_for_users(u_b, u_b, p_other)
        )
        f_b = self.Finding.sudo().create(
            {
                "name": "F on B",
                "engagement_id": e_b.id,
            }
        )
        a_visible = self.Engagement.with_user(u_a).search(
            [("id", "in", [e_a.id, e_b.id])]
        )
        self.assertEqual(a_visible, e_a)
        a_findings = self.Finding.with_user(u_a).search(
            [("id", "=", f_b.id)]
        )
        self.assertFalse(a_findings)

    def test_manager_sees_all_company_engagements(self):
        g_mgr = self.env.ref("auditflow_standard.group_audit_manager")
        g_user = self.env.ref("base.group_user")
        mgr = self.env["res.users"].with_context(no_reset_password=True).create(
            {
                "name": "Audit mgr",
                "login": self._login(),
                "password": "m",
                "group_ids": [(6, 0, [g_user.id, g_mgr.id])],
            }
        )
        p2 = self.env["res.partner"].create(
            {"name": "P2", "company_id": self.company.id}
        )
        e1 = self.Engagement.sudo().create(
            self._engagement_vals_for_users(mgr, mgr, self.auditee_partner)
        )
        e2 = self.Engagement.sudo().create(
            self._engagement_vals_for_users(mgr, mgr, p2)
        )
        found = self.Engagement.with_user(mgr).search(
            [("id", "in", [e1.id, e2.id])]
        )
        self.assertEqual(len(found), 2)

    def test_system_user_can_read_all_engagements(self):
        u_sys = self.env.ref("base.user_admin")
        p2 = self.env["res.partner"].create(
            {"name": "P sys", "company_id": self.company.id}
        )
        e1 = self.Engagement.sudo().create(
            self._engagement_vals_for_users(u_sys, u_sys, self.auditee_partner)
        )
        e2 = self.Engagement.sudo().create(
            self._engagement_vals_for_users(u_sys, u_sys, p2)
        )
        all_e = self.Engagement.with_user(u_sys).search(
            [("id", "in", [e1.id, e2.id])]
        )
        self.assertEqual(len(all_e), 2)

    def test_auditee_read_only_sees_own_engagement_and_findings(self):
        g_auditee = self.env.ref(
            "auditflow_standard.group_audit_auditee"
        )
        g_portal = self.env.ref("base.group_portal")
        p_mine = self.env["res.partner"].create(
            {"name": "My org", "company_id": self.company.id}
        )
        u_auditee = self.env["res.users"].with_context(no_reset_password=True).create(
            {
                "name": "Auditee user",
                "login": self._login(),
                "password": "p",
                "group_ids": [(6, 0, [g_portal.id, g_auditee.id])],
                "partner_id": p_mine.id,
            }
        )
        p_other = self.env["res.partner"].create(
            {"name": "Other org", "company_id": self.company.id}
        )
        e_own = self.Engagement.sudo().create(
            self._engagement_vals_for_users(
                self.env.user, self.env.user, p_mine
            )
        )
        e_other = self.Engagement.sudo().create(
            self._engagement_vals_for_users(
                self.env.user, self.env.user, p_other
            )
        )
        f_own = self.Finding.sudo().create(
            {"name": "F own", "engagement_id": e_own.id}
        )
        my_eng = self.Engagement.with_user(u_auditee).search(
            [("id", "in", [e_own.id, e_other.id])]
        )
        self.assertEqual(my_eng, e_own)
        my_find = self.Finding.with_user(u_auditee).search(
            [("id", "=", f_own.id)]
        )
        self.assertTrue(my_find)
        with self.assertRaises(AccessError):
            e_own.with_user(u_auditee).write({"scope": "Changed"})
        with self.assertRaises(AccessError):
            f_own.with_user(u_auditee).write({"name": "Changed name"})


@tagged("post_install", "-at_install", "auditflow", "auditflow_dashboard_acl")
class TestAuditDashboardAccess(TransactionCase):
    """Dashboard RPC must follow ir.access on the service and on the records."""

    @classmethod
    def _gc_filestore(cls):
        # TransactionCase garbage-collects the filestore after the class.
        # Leave the dedicated filestore and checklist markers untouched.
        return None

    def setUp(self):
        super().setUp()
        self.env = self.env(context=dict(
            self.env.context,
            no_reset_password=True,
            mail_create_nolog=True,
            mail_create_nosubscribe=True,
            tracking_disable=True,
        ))
        self.Engagement = self.env["audit.engagement"]
        self.Finding = self.env["audit.finding"]
        self.Capa = self.env["audit.corrective.action"]
        self.Service = self.env["audit.dashboard.service"]

    def _login(self):
        return "u_%s" % uuid.uuid4().hex[:12]

    def _create_user(self, name, group_xmlids, partner=None):
        """Create a user without writing an avatar attachment."""
        group_ids = [self.env.ref(xmlid).id for xmlid in group_xmlids]
        vals = {
            "name": name,
            "login": self._login(),
            "password": "x",
            "group_ids": [(6, 0, group_ids)],
        }
        if partner is not None:
            vals["partner_id"] = partner.id
        partner_cls = type(self.env["res.partner"])
        with patch.object(partner_cls, "_avatar_generate_svg", lambda _self: False):
            return self.env["res.users"].create(vals)

    def _env_as(self, user):
        context = dict(self.env.context, allowed_company_ids=user.company_ids.ids)
        return self.env(user=user, context=context, su=False)

    def _engagement_vals(self, lead, auditors, auditee, company):
        today = fields.Date.context_today(self.env.user)
        return {
            "auditee_id": auditee.id,
            "lead_auditor_id": lead.id,
            "auditor_ids": [(6, 0, auditors.ids)],
            "start_date": today,
            "end_date": today + timedelta(days=30),
            "scope": "S",
            "objectives": "O",
            "company_id": company.id,
        }

    def _assert_dashboard_denied(self, user):
        service = self._env_as(user)["audit.dashboard.service"]
        with self.assertRaises(AccessError):
            service.get_dashboard_summary()
        with self.assertRaises(AccessError):
            service.get_dashboard_summary(
                {"status": "open", "severity": "critical"}
            )
        with self.assertRaises(AccessError):
            service.get_dashboard_graph_data("critical_findings")
        with self.assertRaises(AccessError):
            service.get_dashboard_graph_data("capa_overdue")
        with self.assertRaises(AccessError):
            service.get_dashboard_filters_data()

    def _disjoint_auditor_case(self):
        token = uuid.uuid4().hex[:8]
        company = self.env.company
        user_a = self._create_user(
            "Dash ACL auditor A %s" % token,
            ["base.group_user", "auditflow_standard.group_audit_auditor"],
        )
        user_b = self._create_user(
            "Dash ACL auditor B %s" % token,
            ["base.group_user", "auditflow_standard.group_audit_auditor"],
        )
        partner_a = self.env["res.partner"].create(
            {"name": "Dash ACL entity A %s" % token, "company_id": company.id}
        )
        partner_b = self.env["res.partner"].create(
            {"name": "Dash ACL entity B %s" % token, "company_id": company.id}
        )
        eng_a = self.Engagement.sudo().create(
            self._engagement_vals(user_a, user_a, partner_a, company)
        )
        eng_b = self.Engagement.sudo().create(
            self._engagement_vals(user_b, user_b, partner_b, company)
        )
        due = fields.Date.context_today(self.env.user) + timedelta(days=14)
        finding_a = self.Finding.sudo().create(
            {
                "name": "Dash ACL finding A %s" % token,
                "engagement_id": eng_a.id,
                "severity": "critical",
                "status": "open",
                "owner_id": user_a.id,
                "responsible_id": user_a.id,
                "due_date": due,
            }
        )
        finding_b = self.Finding.sudo().create(
            {
                "name": "Dash ACL finding B %s" % token,
                "engagement_id": eng_b.id,
                "severity": "critical",
                "status": "open",
                "owner_id": user_b.id,
                "responsible_id": user_b.id,
                "due_date": due,
            }
        )
        today = fields.Date.context_today(self.env.user)
        capa_a = self.Capa.sudo().create(
            {
                "name": "Dash ACL capa A %s" % token,
                "finding_id": finding_a.id,
                "action_owner_id": user_a.id,
                "target_date": today - timedelta(days=4),
                "state": "in_progress",
                "priority": "high",
            }
        )
        capa_b = self.Capa.sudo().create(
            {
                "name": "Dash ACL capa B %s" % token,
                "finding_id": finding_b.id,
                "action_owner_id": user_b.id,
                "target_date": today - timedelta(days=4),
                "state": "in_progress",
                "priority": "high",
            }
        )
        return {
            "user_a": user_a,
            "user_b": user_b,
            "partner_a": partner_a,
            "partner_b": partner_b,
            "eng_a": eng_a,
            "eng_b": eng_b,
            "finding_a": finding_a,
            "finding_b": finding_b,
            "capa_a": capa_a,
            "capa_b": capa_b,
        }

    def test_plain_internal_user_dashboard_methods_raise_access_error(self):
        user = self._create_user("Dash ACL plain", ["base.group_user"])
        partner = self.env["res.partner"].create(
            {
                "name": "Dash ACL plain entity %s" % uuid.uuid4().hex[:8],
                "company_id": self.env.company.id,
            }
        )
        self.Engagement.sudo().create(
            self._engagement_vals(self.env.user, self.env.user, partner, self.env.company)
        )
        self.assertFalse(user.has_group("auditflow_standard.group_audit_auditor"))
        self._assert_dashboard_denied(user)

    def test_portal_auditee_dashboard_methods_raise_access_error(self):
        token = uuid.uuid4().hex[:8]
        own_partner = self.env["res.partner"].create(
            {"name": "Dash ACL auditee org %s" % token, "company_id": self.env.company.id}
        )
        other_partner = self.env["res.partner"].create(
            {"name": "Dash ACL other org %s" % token, "company_id": self.env.company.id}
        )
        user = self._create_user(
            "Dash ACL auditee %s" % token,
            ["base.group_portal", "auditflow_standard.group_audit_auditee"],
            partner=own_partner,
        )
        self.Engagement.sudo().create(
            self._engagement_vals(self.env.user, self.env.user, own_partner, self.env.company)
        )
        self.Engagement.sudo().create(
            self._engagement_vals(self.env.user, self.env.user, other_partner, self.env.company)
        )
        self.assertTrue(user.has_group("auditflow_standard.group_audit_auditee"))
        self.assertFalse(user.has_group("auditflow_standard.group_audit_auditor"))
        self._assert_dashboard_denied(user)

    def test_auditor_dashboard_limited_to_assigned_records(self):
        case = self._disjoint_auditor_case()
        user_a = case["user_a"]
        env_a = self._env_as(user_a)
        service = env_a["audit.dashboard.service"]
        summary = service.get_dashboard_summary()

        self.assertEqual(env_a["audit.engagement"].search_count([]), 1)
        self.assertEqual(
            env_a["audit.engagement"].search([("id", "=", case["eng_a"].id)]).ids,
            [case["eng_a"].id],
        )
        self.assertFalse(
            env_a["audit.engagement"].search([("id", "=", case["eng_b"].id)])
        )
        self.assertFalse(env_a["audit.finding"].search([("id", "=", case["finding_b"].id)]))
        self.assertFalse(env_a["audit.corrective.action"].search([("id", "=", case["capa_b"].id)]))
        self.assertTrue(case["capa_a"].is_overdue)
        self.assertTrue(case["capa_b"].is_overdue)

        self.assertEqual(summary["total_engagements"], 1)
        self.assertEqual(summary["open_findings"], 1)
        self.assertEqual(summary["critical_findings"], 1)
        self.assertEqual(summary["capa_total"], 1)
        self.assertEqual(summary["capa_open"], 1)
        self.assertEqual(summary["capa_overdue"], 1)
        self.assertEqual(summary["capa_high_risk_open"], 1)
        self.assertEqual(
            summary["total_engagements"],
            env_a["audit.engagement"].search_count([]),
        )
        self.assertEqual(
            summary["open_findings"],
            env_a["audit.finding"].search_count([("status", "=", "open")]),
        )
        self.assertEqual(
            summary["critical_findings"],
            env_a["audit.finding"].search_count([("severity", "=", "critical")]),
        )
        self.assertEqual(
            summary["capa_total"],
            env_a["audit.corrective.action"].search_count([]),
        )
        self.assertLess(
            summary["total_engagements"],
            self.Engagement.sudo().search_count([]),
        )
        self.assertLess(
            summary["critical_findings"],
            self.Finding.sudo().search_count([("severity", "=", "critical")]),
        )

        auditee_a = case["partner_a"].with_env(env_a).display_name
        auditee_b = case["partner_b"].display_name
        graph = service.get_dashboard_graph_data("critical_findings")
        self.assertIn(auditee_a, graph["labels"])
        self.assertNotIn(auditee_b, graph["labels"])
        self.assertNotIn(case["partner_b"].name, graph["labels"])
        self.assertEqual(sum(graph["values"]), 1)

        overdue = service.get_dashboard_graph_data("capa_overdue")
        self.assertIn(case["eng_a"].with_env(env_a).display_name, overdue["labels"])
        self.assertNotIn(case["eng_b"].display_name, overdue["labels"])
        self.assertEqual(sum(overdue["values"]), 1)

        filters = service.get_dashboard_filters_data()
        auditee_ids = {row["id"] for row in filters["auditees"]}
        auditor_ids = {row["id"] for row in filters["auditors"]}
        auditee_names = {row["name"] for row in filters["auditees"]}
        auditor_names = {row["name"] for row in filters["auditors"]}
        self.assertEqual(auditee_ids, {case["partner_a"].id})
        self.assertEqual(auditor_ids, {user_a.id})
        self.assertNotIn(case["partner_b"].id, auditee_ids)
        self.assertNotIn(case["user_b"].id, auditor_ids)
        self.assertNotIn(case["partner_b"].name, auditee_names)
        self.assertNotIn(case["user_b"].name, auditor_names)
        self.assertIn("open", filters["statuses"])
        self.assertIn("critical", filters["severities"])

    def test_auditor_filtered_finding_metrics_respect_caller_access(self):
        case = self._disjoint_auditor_case()
        user_a = case["user_a"]
        env_a = self._env_as(user_a)
        service = env_a["audit.dashboard.service"]
        filters = {"status": "open", "severity": "critical"}
        summary = service.get_dashboard_summary(filters)

        caller_findings = env_a["audit.finding"].search(
            [("status", "=", "open"), ("severity", "=", "critical")]
        )
        caller_engagement_ids = caller_findings.mapped("engagement_id").ids
        sudo_engagement_ids = self.Finding.sudo().search(
            [
                ("status", "=", "open"),
                ("severity", "=", "critical"),
                ("id", "in", [case["finding_a"].id, case["finding_b"].id]),
            ]
        ).mapped("engagement_id").ids

        self.assertEqual(set(sudo_engagement_ids), {case["eng_a"].id, case["eng_b"].id})
        self.assertEqual(caller_engagement_ids, [case["eng_a"].id])
        self.assertNotIn(case["eng_b"].id, caller_engagement_ids)
        self.assertEqual(summary["total_engagements"], 1)
        self.assertEqual(summary["open_findings"], 1)
        self.assertEqual(summary["critical_findings"], 1)
        self.assertEqual(
            summary["total_engagements"],
            env_a["audit.engagement"].search_count(
                [("id", "in", caller_engagement_ids)]
            ),
        )
        self.assertEqual(
            summary["open_findings"],
            env_a["audit.finding"].search_count(
                [("status", "=", "open"), ("severity", "=", "critical")]
            ),
        )
        self.assertLess(summary["total_engagements"], len(sudo_engagement_ids))

        graph = service.get_dashboard_graph_data("critical_findings", filters)
        self.assertIn(case["partner_a"].with_env(env_a).display_name, graph["labels"])
        self.assertNotIn(case["partner_b"].display_name, graph["labels"])
        self.assertNotIn(case["partner_b"].name, graph["labels"])
        self.assertEqual(sum(graph["values"]), 1)

    def test_manager_dashboard_includes_own_company_excludes_other_company(self):
        token = uuid.uuid4().hex[:8]
        manager = self._create_user(
            "Dash ACL manager %s" % token,
            ["base.group_user", "auditflow_standard.group_audit_manager"],
        )
        company_cls = type(self.env["res.company"])
        with patch.object(company_cls, "_get_logo", lambda _self: False):
            other_company = self.env["res.company"].create(
                {"name": "Dash ACL other company %s" % token, "logo": False}
            )
        self.assertNotIn(other_company, manager.company_ids)

        partner_own = self.env["res.partner"].create(
            {
                "name": "Dash ACL home entity %s" % token,
                "company_id": self.env.company.id,
            }
        )
        partner_other = self.env["res.partner"].create(
            {
                "name": "Dash ACL foreign entity %s" % token,
                "company_id": other_company.id,
            }
        )
        eng_own = self.Engagement.sudo().create(
            self._engagement_vals(manager, manager, partner_own, self.env.company)
        )
        eng_other = self.Engagement.sudo().create(
            self._engagement_vals(
                self.env.user, self.env.user, partner_other, other_company
            )
        )
        due = fields.Date.context_today(self.env.user) + timedelta(days=14)
        self.Finding.sudo().create(
            {
                "name": "Dash ACL home finding %s" % token,
                "engagement_id": eng_own.id,
                "severity": "critical",
                "status": "open",
                "owner_id": manager.id,
                "due_date": due,
            }
        )
        self.Finding.sudo().create(
            {
                "name": "Dash ACL foreign finding %s" % token,
                "engagement_id": eng_other.id,
                "severity": "critical",
                "status": "open",
                "owner_id": self.env.user.id,
                "due_date": due,
            }
        )

        env_m = self._env_as(manager)
        service = env_m["audit.dashboard.service"]
        summary = service.get_dashboard_summary()

        self.assertEqual(env_m["audit.engagement"].search_count([("id", "=", eng_own.id)]), 1)
        self.assertEqual(env_m["audit.engagement"].search_count([("id", "=", eng_other.id)]), 0)
        self.assertEqual(
            summary["total_engagements"],
            env_m["audit.engagement"].search_count([]),
        )
        self.assertEqual(
            summary["critical_findings"],
            env_m["audit.finding"].search_count([("severity", "=", "critical")]),
        )
        self.assertEqual(
            summary["open_findings"],
            env_m["audit.finding"].search_count([("status", "=", "open")]),
        )
        self.assertLess(
            summary["total_engagements"],
            self.Engagement.sudo().search_count([]),
        )
        self.assertGreaterEqual(summary["total_engagements"], 1)
        self.assertGreaterEqual(summary["critical_findings"], 1)

        graph = service.get_dashboard_graph_data("critical_findings")
        self.assertIn(partner_own.with_env(env_m).display_name, graph["labels"])
        self.assertNotIn(partner_other.display_name, graph["labels"])
        self.assertNotIn(partner_other.name, graph["labels"])
        self.assertFalse(
            any(partner_other.name in (label or "") for label in graph["labels"])
        )

        filters = service.get_dashboard_filters_data()
        auditee_ids = {row["id"] for row in filters["auditees"]}
        auditee_names = {row["name"] for row in filters["auditees"]}
        self.assertIn(partner_own.id, auditee_ids)
        self.assertNotIn(partner_other.id, auditee_ids)
        self.assertNotIn(partner_other.name, auditee_names)
        self.assertIn(partner_own.with_env(env_m).display_name, auditee_names)


class _PortalSession:
    debug = ""

    def get(self, key, default=None):
        return default


class _PortalRequest:
    """Stand-in for the HTTP request local, without opening a socket."""

    def __init__(self, env):
        self.env = env
        self.db = None
        self.session = _PortalSession()
        self.redirects = []
        self.renders = []

    def redirect(self, url, code=303, local=True):
        from odoo.http import Response

        self.redirects.append(url)
        response = Response(status=code)
        response.headers["Location"] = url
        return response

    def render(self, template, values=None, lazy=True, **kwargs):
        from odoo.http import Response

        payload = values or {}
        self.renders.append((template, payload))
        return Response(template=template, qcontext=payload)


@tagged("post_install", "-at_install", "auditflow", "auditflow_portal")
class TestAuditPortalAccess(TransactionCase):
    """Portal list and detail must follow ir.access without an HTTP server."""

    @classmethod
    def _gc_filestore(cls):
        # TransactionCase garbage-collects the filestore after the class.
        # Leave the dedicated filestore and checklist markers untouched.
        return None

    def setUp(self):
        super().setUp()
        self.env = self.env(context=dict(
            self.env.context,
            no_reset_password=True,
            mail_create_nolog=True,
            mail_create_nosubscribe=True,
            tracking_disable=True,
        ))
        self.Plan = self.env["audit.plan.stable"]
        self.Indicator = self.env["audit.indicator.stable"]

    def _login(self):
        return "u_%s" % uuid.uuid4().hex[:12]

    def _create_user(self, name, group_xmlids, partner=None):
        group_ids = [self.env.ref(xmlid).id for xmlid in group_xmlids]
        vals = {
            "name": name,
            "login": self._login(),
            "password": "x",
            "group_ids": [(6, 0, group_ids)],
        }
        if partner is not None:
            vals["partner_id"] = partner.id
        partner_cls = type(self.env["res.partner"])
        with patch.object(partner_cls, "_avatar_generate_svg", lambda _self: False):
            return self.env["res.users"].create(vals)

    def _call(self, user, method_name, *args, **kwargs):
        from odoo.addons.auditflow_standard.controllers.portal import SmartAuditPortal
        from odoo.http import request_var

        env = self.env(
            user=user,
            context=dict(self.env.context, allowed_company_ids=user.company_ids.ids),
            su=False,
        )
        fake = _PortalRequest(env)
        controller = SmartAuditPortal()
        token = request_var.set(fake)
        try:
            result = getattr(controller, method_name)(*args, **kwargs)
        finally:
            request_var.reset(token)
        return fake, result

    def _plan_vals(self, client, state):
        today = fields.Date.context_today(self.env.user)
        return {
            "client_id": client.id,
            "lead_auditor_id": self.env.user.id,
            "state": state,
            "start_date": today,
            "end_date": today + timedelta(days=30),
            "company_id": self.env.company.id,
        }

    def test_auditee_portal_list_shows_only_readable_plans(self):
        token = uuid.uuid4().hex[:8]
        client = self.env["res.partner"].create({
            "name": "Portal auditee %s" % token,
            "company_id": self.env.company.id,
        })
        other = self.env["res.partner"].create({
            "name": "Portal other client %s" % token,
            "company_id": self.env.company.id,
        })
        auditee = self._create_user(
            "Portal auditee user %s" % token,
            ["base.group_portal", "auditflow_standard.group_audit_auditee"],
            partner=client,
        )
        visible = self.Plan.sudo().create(self._plan_vals(client, "open"))
        draft = self.Plan.sudo().create(self._plan_vals(client, "draft"))
        foreign = self.Plan.sudo().create(self._plan_vals(other, "open"))

        fake, result = self._call(auditee, "portal_my_audit")

        self.assertFalse(fake.redirects)
        self.assertEqual(result.template, "auditflow_standard.portal_my_audit")
        shown = result.qcontext["plans"]
        self.assertEqual(shown, visible)
        self.assertNotIn(draft, shown)
        self.assertNotIn(foreign, shown)

    def test_user_without_plan_read_access_is_redirected(self):
        token = uuid.uuid4().hex[:8]
        client = self.env["res.partner"].create({
            "name": "Portal denied client %s" % token,
            "company_id": self.env.company.id,
        })
        plain = self._create_user(
            "Portal plain user %s" % token,
            ["base.group_user"],
        )
        plan = self.Plan.sudo().create(self._plan_vals(client, "open"))
        missing_id = plan.id + 100000
        self.assertFalse(self.Plan.sudo().browse(missing_id).exists())

        listed, list_result = self._call(plain, "portal_my_audit")
        self.assertEqual(listed.redirects, ["/my"])
        self.assertFalse(listed.renders)
        self.assertEqual(list_result.headers["Location"], "/my")

        denied, denied_result = self._call(plain, "portal_view_plan", plan.id)
        self.assertEqual(denied.redirects, ["/my"])
        self.assertFalse(denied.renders)
        self.assertEqual(denied_result.headers["Location"], "/my")

        missing, missing_result = self._call(plain, "portal_view_plan", missing_id)
        self.assertEqual(missing.redirects, ["/my"])
        self.assertFalse(missing.renders)
        self.assertEqual(missing_result.headers["Location"], "/my")

    def test_detail_hides_indicators_the_user_cannot_read(self):
        token = uuid.uuid4().hex[:8]
        client = self.env["res.partner"].create({
            "name": "Portal indicator client %s" % token,
            "company_id": self.env.company.id,
        })
        auditee = self._create_user(
            "Portal indicator auditee %s" % token,
            ["base.group_portal", "auditflow_standard.group_audit_auditee"],
            partner=client,
        )
        plan = self.Plan.sudo().create(self._plan_vals(client, "open"))
        visible = self.Indicator.sudo().create({
            "name": "Visible indicator %s" % token,
            "plan_id": plan.id,
            "target": 10.0,
            "current_value": 4.0,
        })
        hidden = self.Indicator.sudo().create({
            "name": "Hidden indicator %s" % token,
            "plan_id": plan.id,
            "target": 10.0,
            "current_value": 9.0,
        })
        company_cls = type(self.env["res.company"])
        with patch.object(company_cls, "_get_logo", lambda _self: False):
            other_company = self.env["res.company"].create({
                "name": "Portal other company %s" % token,
                "logo": False,
            })
        self.assertNotIn(other_company, auditee.company_ids)
        self.env.cr.execute(
            "UPDATE audit_indicator_stable SET company_id = %s WHERE id = %s",
            (other_company.id, hidden.id),
        )
        self.env.invalidate_all()

        self.assertEqual(
            self.Indicator.sudo().search([("id", "=", hidden.id)]).plan_id,
            plan,
        )
        readable = self.Indicator.with_user(auditee).search([
            ("plan_id", "=", plan.id),
        ])
        self.assertIn(visible, readable)
        self.assertNotIn(hidden, readable)

        fake, result = self._call(auditee, "portal_view_plan", plan.id)

        self.assertFalse(fake.redirects)
        self.assertEqual(result.template, "auditflow_standard.portal_audit_plan")
        values = result.qcontext
        self.assertEqual(values["plan"], plan)
        self.assertFalse(values["plan"].env.su)
        self.assertFalse(values["indicators"].env.su)
        self.assertIn(visible, values["indicators"])
        self.assertNotIn(hidden, values["indicators"])
        self.assertNotIn(hidden.name, values["indicators"].mapped("name"))

        html = self._render_source_portal_detail(auditee, values)
        self.assertIn(visible.name, html)
        self.assertNotIn(hidden.name, html)

    def test_source_portal_plan_template_uses_filtered_indicators(self):
        """The on-disk detail template iterates the filtered indicator set.

        This reads ``views/portal_templates.xml`` only. It does not load
        the installed ``ir.ui.view`` architecture.
        """
        import odoo.modules.module as odoo_module
        from lxml import etree

        path = (
            Path(odoo_module.get_module_path("auditflow_standard"))
            / "views"
            / "portal_templates.xml"
        )
        root = etree.parse(str(path))
        template = root.find(".//template[@id='portal_audit_plan']")
        call = template[0]
        self.assertEqual(call.get("t-call"), "portal.portal_layout")
        source_xml = etree.tostring(call, encoding=str)
        self.assertIn('t-foreach="indicators"', source_xml)
        self.assertNotIn("plan.indicator_ids", source_xml)

    def _render_source_portal_detail(self, user, values):
        """QWeb-render the source detail body in the caller's environment.

        ``portal.frontend_layout`` reads ``request.csrf_token`` and
        ``request.httprequest``. Those exist only on a real HTTP request,
        so this renders the source template's own container, which is the
        markup that lists indicators. It does not load view 674.
        """
        import odoo.modules.module as odoo_module
        from lxml import etree
        from odoo.http import request_var

        path = (
            Path(odoo_module.get_module_path("auditflow_standard"))
            / "views"
            / "portal_templates.xml"
        )
        root = etree.parse(str(path))
        template = root.find(".//template[@id='portal_audit_plan']")
        call = template[0]
        self.assertEqual(call.get("t-call"), "portal.portal_layout")
        arch = etree.Element("t")
        arch.append(call[0])
        env = self.env(
            user=user,
            context=dict(
                self.env.context,
                allowed_company_ids=user.company_ids.ids,
            ),
            su=False,
        )
        fake = _PortalRequest(env)
        token = request_var.set(fake)
        try:
            return env["ir.qweb"]._render(arch, dict(values))
        finally:
            request_var.reset(token)
