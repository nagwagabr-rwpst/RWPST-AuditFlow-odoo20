# Part of RWPST AuditFlow. See module manifest for license.

from datetime import timedelta

from odoo import fields
from odoo.exceptions import ValidationError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged("post_install", "-at_install", "auditflow")
class TestAuditFindingDueStatus(TransactionCase):
    def setUp(self):
        super().setUp()
        g_mgr = self.env.ref("auditflow_standard.group_audit_manager")
        if g_mgr not in self.env.user.group_ids:
            self.env.user.sudo().write(
                {"group_ids": [(4, g_mgr.id)]}
            )
        self.Engagement = self.env["audit.engagement"]
        self.Finding = self.env["audit.finding"]
        self.Icp = self.env["ir.config_parameter"].sudo()
        self.user = self.env.user
        self.partner = self.user.partner_id
        if not self.partner:
            self.partner = self.env["res.partner"].create(
                {"name": "Test user partner", "company_id": self.env.company.id}
            )

    def _engagement_vals(self):
        today = fields.Date.context_today(self.user)
        return {
            "auditee_id": self.partner.id,
            "lead_auditor_id": self.user.id,
            "auditor_ids": [(6, 0, [self.user.id])],
            "start_date": today,
            "end_date": today + timedelta(days=30),
        }

    def test_01_yesterday_open_overdue(self):
        today = fields.Date.context_today(self.user)
        e = self.Engagement.create(self._engagement_vals())
        f = self.Finding.create(
            {
                "name": "F1",
                "engagement_id": e.id,
                "status": "open",
                "due_date": today - timedelta(days=1),
            }
        )
        self.assertTrue(f.is_overdue)
        self.assertFalse(f.is_due_soon)

    def test_02_today_open_due_soon(self):
        today = fields.Date.context_today(self.user)
        e = self.Engagement.create(self._engagement_vals())
        f = self.Finding.create(
            {
                "name": "F2",
                "engagement_id": e.id,
                "status": "open",
                "due_date": today,
            }
        )
        self.assertFalse(f.is_overdue)
        self.assertTrue(f.is_due_soon)

    def test_03_due_within_default_window(self):
        today = fields.Date.context_today(self.user)
        e = self.Engagement.create(self._engagement_vals())
        f = self.Finding.create(
            {
                "name": "F3",
                "engagement_id": e.id,
                "status": "open",
                "due_date": today + timedelta(days=3),
            }
        )
        self.assertTrue(f.is_due_soon)

    def test_04_due_after_configured_range_not_due_soon(self):
        today = fields.Date.context_today(self.user)
        e = self.Engagement.create(self._engagement_vals())
        # Default due_soon_days=7: end = add(today, 7) — due later than that is not “soon”
        past_end = today + timedelta(days=8)
        f = self.Finding.create(
            {
                "name": "F4",
                "engagement_id": e.id,
                "status": "open",
                "due_date": past_end,
            }
        )
        self.assertFalse(f.is_due_soon)

    def test_05_status_done_clears_overdue(self):
        today = fields.Date.context_today(self.user)
        e = self.Engagement.create(self._engagement_vals())
        f = self.Finding.create(
            {
                "name": "F5",
                "engagement_id": e.id,
                "status": "done",
                "due_date": today - timedelta(days=1),
            }
        )
        self.assertFalse(f.is_overdue)
        self.assertFalse(f.is_due_soon)

    def test_06_status_cancelled_clears_overdue(self):
        today = fields.Date.context_today(self.user)
        e = self.Engagement.create(self._engagement_vals())
        f = self.Finding.create(
            {
                "name": "F6",
                "engagement_id": e.id,
                "status": "cancelled",
                "due_date": today - timedelta(days=1),
            }
        )
        self.assertFalse(f.is_overdue)
        self.assertFalse(f.is_due_soon)

    def test_07_critical_missing_due_date_raises(self):
        e = self.Engagement.create(self._engagement_vals())
        with self.assertRaises(ValidationError):
            self.Finding.create(
                {
                    "name": "Crit",
                    "engagement_id": e.id,
                    "severity": "critical",
                    "status": "open",
                }
            )

    def test_08_critical_with_due_date_creates(self):
        today = fields.Date.context_today(self.user)
        e = self.Engagement.create(self._engagement_vals())
        f = self.Finding.create(
            {
                "name": "Crit ok",
                "engagement_id": e.id,
                "severity": "critical",
                "status": "open",
                "owner_id": self.user.id,
                "due_date": today,
            }
        )
        self.assertTrue(f)

    def test_09_10_11_engagement_counts_and_recompute(self):
        today = fields.Date.context_today(self.user)
        e = self.Engagement.create(self._engagement_vals())
        self.Finding.create(
            {
                "name": "Overdue",
                "engagement_id": e.id,
                "status": "open",
                "due_date": today - timedelta(days=1),
            }
        )
        self.Finding.create(
            {
                "name": "Soon",
                "engagement_id": e.id,
                "status": "open",
                "due_date": today + timedelta(days=2),
            }
        )
        e = self.Engagement.browse(e.id)
        self.assertEqual(e.overdue_finding_count, 1)
        self.assertEqual(e.due_soon_finding_count, 1)
        overdue = e.finding_ids.filtered("is_overdue")
        overdue.write({"status": "done"})
        e = self.Engagement.browse(e.id)
        self.assertEqual(e.overdue_finding_count, 0)
        self.assertEqual(e.due_soon_finding_count, 1)
        e.finding_ids.filtered("is_due_soon").write({"status": "done"})
        e = self.Engagement.browse(e.id)
        self.assertEqual(e.due_soon_finding_count, 0)

    def _due_soon_param_state(self, key):
        """Existing row plus its stored value. Empty means the key is absent.

        ``get_str`` returns the default for both a missing row and a NULL
        value. The record's ``value`` keeps NULL (False) and '' distinct.
        """
        record = self.Icp.search([('key', '=', key)], limit=1)
        return record, (record.value if record else False)

    def _restore_due_soon_param(self, key, record, value):
        """Restore the captured row, or unlink only a row this test created."""
        if record:
            current = record.exists()
            if current:
                current.write({'value': value})
            return
        created = self.Icp.search([('key', '=', key)], limit=1)
        if created and created.id not in record.ids:
            created.unlink()

    def test_12_due_soon_respects_param_change(self):
        key = "fine_tech_smart_audit.due_soon_days"
        record, value = self._due_soon_param_state(key)
        try:
            self.Icp.set_str(key, "3")
            today = fields.Date.context_today(self.user)
            e = self.Engagement.create(self._engagement_vals())
            f = self.Finding.create(
                {
                    "name": "Far",
                    "engagement_id": e.id,
                    "status": "open",
                    "due_date": today + timedelta(days=5),
                }
            )
            self.assertFalse(f.is_due_soon)
        finally:
            self._restore_due_soon_param(key, record, value)

    def test_recompute_after_write_due_status(self):
        today = fields.Date.context_today(self.user)
        e = self.Engagement.create(self._engagement_vals())
        f = self.Finding.create(
            {
                "name": "Move",
                "engagement_id": e.id,
                "status": "open",
                "due_date": today + timedelta(days=10),
            }
        )
        self.assertFalse(f.is_due_soon)
        f.write({"due_date": today + timedelta(days=1)})
        self.assertTrue(f.is_due_soon)

    def test_invalid_icp_falls_back(self):
        key = "fine_tech_smart_audit.due_soon_days"
        record, value = self._due_soon_param_state(key)
        try:
            self.Icp.set_str(key, "not-a-number")
            n = self.Finding._get_due_soon_days()
            self.assertEqual(n, 7)
        finally:
            self._restore_due_soon_param(key, record, value)

    def test_action_view_overdue_context_and_domain(self):
        e = self.Engagement.create(self._engagement_vals())
        act = e.action_view_overdue_findings()
        self.assertEqual(
            [("engagement_id", "=", e.id), ("is_overdue", "=", True)],
            act.get("domain"),
        )
        self.assertEqual(act["context"].get("default_engagement_id"), e.id)
        self.assertTrue(act["context"].get("search_default_filter_overdue"))

    def test_multiple_findings_under_engagement(self):
        today = fields.Date.context_today(self.user)
        e = self.Engagement.create(self._engagement_vals())
        for i in range(3):
            self.Finding.create(
                {
                    "name": "M%s" % i,
                    "engagement_id": e.id,
                    "status": "open",
                    "due_date": today - timedelta(days=1),
                }
            )
        e = self.Engagement.browse(e.id)
        self.assertEqual(e.overdue_finding_count, 3)
