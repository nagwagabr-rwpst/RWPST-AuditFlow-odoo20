# Part of RWPST AuditFlow. See module manifest for license.

from datetime import timedelta

from odoo import fields
from odoo.exceptions import AccessError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged("post_install", "-at_install", "auditflow")
class TestAuditCorrectiveAction(TransactionCase):
    def setUp(self):
        super().setUp()
        g_mgr = self.env.ref("auditflow_standard.group_audit_manager")
        if g_mgr not in self.env.user.group_ids:
            self.env.user.sudo().write({"group_ids": [(4, g_mgr.id)]})
        self.Capa = self.env["audit.corrective.action"]
        self.Finding = self.env["audit.finding"]
        self.Engagement = self.env["audit.engagement"]
        self.user = self.env.user
        self.partner = self.user.partner_id
        today = fields.Date.context_today(self.env.user)
        self.eng = self.Engagement.create(
            {
                "auditee_id": self.partner.id,
                "lead_auditor_id": self.user.id,
                "auditor_ids": [(6, 0, [self.user.id])],
                "start_date": today,
                "end_date": today + timedelta(days=30),
                "scope": "CAPA test scope",
                "objectives": "CAPA test objectives",
            }
        )
        self.finding = self.Finding.create(
            {
                "name": "Test finding for CAPA",
                "engagement_id": self.eng.id,
                "severity": "medium",
                "status": "open",
                "owner_id": self.user.id,
                "due_date": today + timedelta(days=10),
                "action_plan": "Plan",
                "target_date": today + timedelta(days=20),
                "responsible_id": self.user.id,
                "management_response": "Response text here.",
            }
        )

    def test_capa_overdue_and_days(self):
        today = fields.Date.context_today(self.env.user)
        capa = self.Capa.create(
            {
                "name": "Overdue item",
                "finding_id": self.finding.id,
                "action_owner_id": self.user.id,
                "target_date": today - timedelta(days=5),
                "state": "in_progress",
            }
        )
        self.assertTrue(capa.is_overdue)
        self.assertEqual(capa.days_overdue, 5)

        capa.write({"state": "done", "completion_date": today})
        capa.invalidate_recordset(["is_overdue", "days_overdue"])
        self.assertFalse(capa.is_overdue)
        self.assertEqual(capa.days_overdue, 0)

    def test_state_transitions_and_done_sets_completion_date(self):
        capa = self.Capa.create(
            {
                "name": "Workflow",
                "finding_id": self.finding.id,
                "action_owner_id": self.user.id,
                "target_date": fields.Date.context_today(self.env.user),
                "state": "draft",
            }
        )
        capa.action_assign()
        self.assertEqual(capa.state, "assigned")
        capa.action_start()
        self.assertEqual(capa.state, "in_progress")
        today = fields.Date.context_today(self.env.user)
        capa.action_done()
        self.assertEqual(capa.state, "done")
        self.assertEqual(capa.completion_date, today)
        capa.action_reset_draft()
        self.assertEqual(capa.state, "draft")
        self.assertFalse(capa.completion_date)

    def test_finding_corrective_status_and_engagement_counts(self):
        f = self.finding
        self.assertEqual(f.corrective_status, "no_action")
        c1 = self.Capa.create(
            {
                "name": "A",
                "finding_id": f.id,
                "action_owner_id": self.user.id,
                "target_date": fields.Date.context_today(self.env.user)
                + timedelta(days=30),
                "state": "assigned",
            }
        )
        f.invalidate_recordset()
        self.assertEqual(f.corrective_status, "pending")
        today = fields.Date.context_today(self.env.user)
        c1.write({"target_date": today - timedelta(days=1), "state": "assigned"})
        c1.invalidate_recordset(["is_overdue"])
        f.invalidate_recordset()
        self.assertEqual(f.corrective_status, "overdue")

        c1.write({"state": "done", "completion_date": today})
        f.invalidate_recordset()
        self.assertEqual(f.corrective_status, "completed")

        self.eng.invalidate_recordset()
        self.assertGreaterEqual(self.eng.corrective_action_count, 1)
        self.assertEqual(self.eng.completed_corrective_action_count, 1)

    def test_auditor_cannot_unlink_done_capa(self):
        auditor = self.env["res.users"].create(
            {
                "name": "Auditor capa",
                "login": "auditor_capa_test",
                "email": "auditor_capa@test.example",
                "group_ids": [
                    (
                        6,
                        0,
                        [
                            self.env.ref(
                                "auditflow_standard.group_audit_auditor"
                            ).id,
                            self.env.ref("base.group_user").id,
                        ],
                    )
                ],
            }
        )
        capa = self.Capa.create(
            {
                "name": "Done only",
                "finding_id": self.finding.id,
                "action_owner_id": auditor.id,
                "target_date": fields.Date.context_today(self.env.user),
                "state": "done",
                "completion_date": fields.Date.context_today(self.env.user),
            }
        )
        self.eng.write({"auditor_ids": [(4, auditor.id)]})
        self.assertEqual(capa.state, "done")
        capa_as_auditor = capa.with_user(auditor)
        with self.assertRaises(AccessError):
            capa_as_auditor.unlink()

    def test_manager_may_unlink_done_capa(self):
        capa = self.Capa.create(
            {
                "name": "Done unlink",
                "finding_id": self.finding.id,
                "action_owner_id": self.user.id,
                "target_date": fields.Date.context_today(self.env.user),
                "state": "done",
                "completion_date": fields.Date.context_today(self.env.user),
            }
        )
        capa.unlink()
        self.assertFalse(capa.exists())
