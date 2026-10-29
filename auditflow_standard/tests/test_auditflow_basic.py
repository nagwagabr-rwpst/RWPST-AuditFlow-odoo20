# Part of RWPST AuditFlow. See module manifest for license.

from datetime import timedelta

from odoo import fields
from odoo.exceptions import UserError, ValidationError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged("post_install", "-at_install", "auditflow")
class TestAuditflowBasic(TransactionCase):
    def setUp(self):
        super().setUp()
        g_mgr = self.env.ref("auditflow_standard.group_audit_manager")
        if g_mgr not in self.env.user.group_ids:
            self.env.user.sudo().write(
                {"group_ids": [(4, g_mgr.id)]}
            )
        self.Engagement = self.env["audit.engagement"]
        self.Finding = self.env["audit.finding"]
        self.user = self.env.user
        self.partner = self.user.partner_id
        if not self.partner:
            self.partner = self.env["res.partner"].create(
                {"name": "Test user partner", "company_id": self.env.company.id}
            )
        self.assertTrue(self.env.company, "A company is required for engagements.")

    def _new_engagement_vals(self):
        today = fields.Date.context_today(self.env.user)
        return {
            "auditee_id": self.partner.id,
            "lead_auditor_id": self.user.id,
            "auditor_ids": [(6, 0, [self.user.id])],
            "start_date": today,
            "end_date": today + timedelta(days=30),
            "scope": "Test scope",
            "objectives": "Test objectives",
        }

    def test_engagement_create_sequence_and_draft(self):
        """A) New engagement gets a sequence reference and starts in draft."""
        rec = self.Engagement.create(self._new_engagement_vals())
        self.assertEqual(rec.state, "draft", "default state should be draft")
        self.assertNotEqual(
            rec.name,
            "New",
            "name should be filled from sequence, not the placeholder 'New'",
        )
        self.assertTrue(rec.name, "sequence reference should be non-empty")

    def test_engagement_workflow_states(self):
        """B) Workflow actions set the expected state (model API names)."""
        rec = self.Engagement.create(self._new_engagement_vals())
        rec.action_start_fieldwork()
        self.assertEqual(rec.state, "fieldwork")
        rec.action_move_to_reporting()
        self.assertEqual(rec.state, "reporting")
        rec.action_issue_report()
        self.assertEqual(rec.state, "issued")
        rec.action_close()
        self.assertEqual(rec.state, "closed")
        rec.action_cancel()
        self.assertEqual(rec.state, "cancelled")
        # Return to draft (method name: action_set_to_draft)
        rec.action_set_to_draft()
        self.assertEqual(rec.state, "draft")

    def _minimal_engagement_vals_not_ready(self):
        today = fields.Date.context_today(self.env.user)
        return {
            "auditee_id": self.partner.id,
            "lead_auditor_id": self.user.id,
            "auditor_ids": [(6, 0, [self.user.id])],
            "start_date": today,
            "end_date": today + timedelta(days=30),
        }

    def test_issue_report_opens_wizard_when_not_ready(self):
        """Not report_ready: action opens confirmation wizard (no direct issue)."""
        rec = self.Engagement.create(self._minimal_engagement_vals_not_ready())
        rec.action_start_fieldwork()
        rec.action_move_to_reporting()
        self.assertFalse(rec.report_ready)
        act = rec.action_issue_report()
        self.assertIsInstance(act, dict)
        self.assertEqual(act.get("type"), "ir.actions.act_window")
        self.assertEqual(act.get("res_model"), "audit.engagement.issue.warning.wizard")
        self.assertEqual(act.get("view_mode"), "form")
        self.assertEqual(act.get("target"), "new")
        self.assertEqual(
            (act.get("context") or {}).get("default_engagement_id"), rec.id
        )
        self.assertEqual(rec.state, "reporting")

    def test_issue_report_wizard_force_issue_sets_issued(self):
        """Force Issue from wizard sets engagement state to issued (override)."""
        rec = self.Engagement.create(self._minimal_engagement_vals_not_ready())
        rec.action_start_fieldwork()
        rec.action_move_to_reporting()
        wiz = self.env["audit.engagement.issue.warning.wizard"].create(
            {
                "engagement_id": rec.id,
                "message": rec.report_readiness_message or "",
            }
        )
        wiz.action_force_issue()
        self.assertEqual(rec.state, "issued")

    def test_issue_report_ready_sets_issued_directly(self):
        """report_ready: issue action writes issued without opening wizard."""
        rec = self.Engagement.create(self._new_engagement_vals())
        rec.action_start_fieldwork()
        rec.action_move_to_reporting()
        self.assertTrue(rec.report_ready)
        res = rec.action_issue_report()
        self.assertTrue(res)
        self.assertEqual(rec.state, "issued")

    def test_issue_report_multiple_not_ready_raises_usererror(self):
        """More than one not-ready engagement cannot open the single-record wizard."""
        a = self.Engagement.create(self._minimal_engagement_vals_not_ready())
        b = self.Engagement.create(self._minimal_engagement_vals_not_ready())
        a.action_start_fieldwork()
        a.action_move_to_reporting()
        b.action_start_fieldwork()
        b.action_move_to_reporting()
        with self.assertRaises(UserError):
            (a | b).action_issue_report()

    def test_finding_increments_engagement_finding_count(self):
        """C) Linking a finding to an engagement updates finding_count."""
        engagement = self.Engagement.create(self._new_engagement_vals())
        self.assertEqual(engagement.finding_count, 0)
        self.Finding.create(
            {
                "name": "Test finding",
                "engagement_id": engagement.id,
            }
        )
        engagement.invalidate_recordset()
        self.assertEqual(engagement.finding_count, 1)

    def test_finding_critical_requires_owner_and_due_date(self):
        """D) Critical severity enforces owner and due date."""
        engagement = self.Engagement.create(self._new_engagement_vals())
        with self.assertRaises(ValidationError):
            self.Finding.create(
                {
                    "name": "Critical no owner",
                    "engagement_id": engagement.id,
                    "severity": "critical",
                }
            )
        good = self.Finding.create(
            {
                "name": "Critical complete",
                "engagement_id": engagement.id,
                "severity": "critical",
                "owner_id": self.user.id,
                "due_date": fields.Date.context_today(self.user),
            }
        )
        self.assertEqual(good.severity, "critical")

    def test_action_view_findings(self):
        """E) Smart button returns a window action with domain and default context."""
        engagement = self.Engagement.create(self._new_engagement_vals())
        act = engagement.action_view_findings()
        self.assertEqual(act.get("type"), "ir.actions.act_window")
        self.assertEqual(act.get("res_model"), "audit.finding")
        self.assertIn("domain", act)
        self.assertIn(("engagement_id", "=", engagement.id), act["domain"])
        self.assertIn("context", act)
        self.assertEqual(
            act["context"].get("default_engagement_id"),
            engagement.id,
        )
        self.assertEqual(
            act.get("search_view_id"),
            self.env.ref(
                "auditflow_standard.view_audit_finding_search"
            ).id,
        )

    def test_finding_risk_rating_matrix(self):
        """Risk rating follows impact x likelihood matrix."""
        eng = self.Engagement.create(self._new_engagement_vals())
        f = self.Finding.create(
            {
                "name": "R1",
                "engagement_id": eng.id,
                "risk_impact": "high",
                "risk_likelihood": "high",
            }
        )
        self.assertEqual(f.risk_rating, "critical")
        f.risk_impact = "low"
        f.risk_likelihood = "medium"
        self.assertEqual(f.risk_rating, "low")

    def test_engagement_report_readiness(self):
        """Report readiness requires scope, objectives, and complete open findings."""
        today = fields.Date.context_today(self.env.user)
        vals = self._new_engagement_vals()
        vals["scope"] = "S"
        vals["objectives"] = "O"
        eng = self.Engagement.create(vals)
        self.assertTrue(eng.report_ready, "no findings means ready")
        self.Finding.create(
            {
                "name": "Open item",
                "engagement_id": eng.id,
                "status": "open",
                "severity": "medium",
            }
        )
        self.env.flush_all()
        eng.invalidate_recordset(
            ["report_ready", "report_readiness_message"]
        )
        eng = self.Engagement.browse(eng.id)
        self.assertFalse(eng.report_ready)
        self.Finding.search(
            [("engagement_id", "=", eng.id)]
        ).write(
            {
                "action_plan": "Do the work",
                "target_date": today,
                "responsible_id": self.user.id,
                "management_response": "Acknowledged.",
            }
        )
        self.env.flush_all()
        eng = self.Engagement.browse(eng.id)
        self.assertTrue(eng.report_ready)
