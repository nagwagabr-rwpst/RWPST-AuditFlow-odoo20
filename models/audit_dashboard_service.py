# -*- coding: utf-8 -*-
"""Config-driven dashboard metrics service (JSON-serializable payloads for OWL).

No deprecated odoo.osv usage.
No gettext call at module import time.
"""
from collections import defaultdict

from odoo import _, api, models
from odoo.exceptions import AccessError


DASHBOARD_METRICS = {
    "total_engagements": {
        "label": "Total Engagements",
        "model": "audit.engagement",
        "domain": [],
        "aggregation": "count",
    },
    "open_findings": {
        "label": "Open Review Results",
        "model": "audit.finding",
        "domain": [("status", "=", "open")],
        "aggregation": "count",
    },
    "critical_findings": {
        "label": "High Risk Review Results",
        "model": "audit.finding",
        "domain": [("severity", "=", "critical")],
        "aggregation": "count",
        "group_by": "engagement_id",
        "graph_scope": "critical_by_auditee",
    },
    "overdue_findings": {
        "label": "Delayed Review Results",
        "model": "audit.finding",
        "domain": [("is_overdue", "=", True)],
        "aggregation": "count",
        "group_by": "due_date:day",
    },
    "completed_engagements": {
        "label": "Completed Engagements",
        "model": "audit.engagement",
        "domain": [("state", "=", "closed")],
        "aggregation": "count",
        "group_by": "state",
    },
    "risk_exposure": {
        "label": "Risk level",
        "model": "audit.finding",
        "domain": [],
        "aggregation": "count",
        "group_by": "risk_rating",
    },
    "capa_total": {
        "label": "Total Corrective Actions (CAPA)",
        "model": "audit.corrective.action",
        "domain": [],
        "aggregation": "count",
        "group_by": "state",
    },
    "capa_open": {
        "label": "Open Corrective Actions (CAPA)",
        "model": "audit.corrective.action",
        "domain": [("state", "not in", ("done", "cancelled"))],
        "aggregation": "count",
        "group_by": "priority",
    },
    "capa_overdue": {
        "label": "Delayed Corrective Actions (CAPA)",
        "model": "audit.corrective.action",
        "domain": [("is_overdue", "=", True)],
        "aggregation": "count",
        "group_by": "engagement_id",
    },
    "capa_completed": {
        "label": "Completed Corrective Actions (CAPA)",
        "model": "audit.corrective.action",
        "domain": [("state", "=", "done")],
        "aggregation": "count",
        "group_by": "state",
    },
    "capa_high_risk_open": {
        "label": "High-risk open Corrective Actions (CAPA)",
        "model": "audit.corrective.action",
        "domain": [
            ("state", "not in", ("done", "cancelled")),
            ("priority", "in", ("high", "critical")),
        ],
        "aggregation": "count",
        "group_by": "priority",
    },
}


class AuditDashboardService(models.AbstractModel):
    _name = "audit.dashboard.service"
    _description = "Audit Dashboard Service"

    @api.model
    def _many2one_raw_id(self, raw):
        if isinstance(raw, bool) or not raw:
            return False
        if isinstance(raw, int):
            return raw
        if isinstance(raw, (list, tuple)) and len(raw) >= 1:
            return raw[0]
        rid = getattr(raw, "id", None)
        if isinstance(rid, int) and not isinstance(rid, bool):
            return rid
        ids = getattr(raw, "ids", None)
        if ids:
            return ids[0]
        return False

    @api.model
    def _safe_and(self, domains):
        """Combine domains with explicit '&' polish notation."""
        parts = [list(domain) for domain in domains if domain]
        if not parts:
            return []
        if len(parts) == 1:
            return parts[0]

        result = parts[0]
        for domain in parts[1:]:
            result = ["&"] + result + domain
        return result

    @api.model
    def _normalize_dashboard_filters(self, filters):
        empty = {
            "auditor_id": False,
            "auditee_id": False,
            "status": False,
            "severity": False,
        }

        if not filters:
            return empty

        if isinstance(filters, (list, tuple)):
            filters = filters[0] if filters else {}

        if not isinstance(filters, dict):
            return empty

        def _as_int(value):
            if value in (None, False, ""):
                return False
            try:
                return int(value)
            except (TypeError, ValueError):
                return False

        status = filters.get("status")
        severity = filters.get("severity")

        return {
            "auditor_id": _as_int(filters.get("auditor_id")),
            "auditee_id": _as_int(filters.get("auditee_id")),
            "status": False if status in (False, None, "") else str(status),
            "severity": False if severity in (False, None, "") else str(severity),
        }

    @api.model
    def _domain_auditor_engagement(self, auditor_id):
        return [
            "|",
            ("lead_auditor_id", "=", auditor_id),
            ("auditor_ids", "in", [auditor_id]),
        ]

    @api.model
    def _domain_auditor_finding(self, auditor_id):
        return [
            "|",
            "|",
            "|",
            ("owner_id", "=", auditor_id),
            ("responsible_id", "=", auditor_id),
            ("engagement_id.lead_auditor_id", "=", auditor_id),
            ("engagement_id.auditor_ids", "in", [auditor_id]),
        ]

    @api.model
    def _domain_finding_engagement_links(self, filters):
        parts = []

        if filters.get("auditee_id"):
            parts.append([("engagement_id.auditee_id", "=", filters["auditee_id"])])

        if filters.get("auditor_id"):
            parts.append(self._domain_auditor_finding(filters["auditor_id"]))

        return self._safe_and(parts)

    @api.model
    def _domain_for_finding_metric(self, base_domain, filters):
        parts = [base_domain, self._domain_finding_engagement_links(filters)]

        if filters.get("status"):
            parts.append([("status", "=", filters["status"])])

        if filters.get("severity"):
            parts.append([("severity", "=", filters["severity"])])

        return self._safe_and(parts)

    @api.model
    def _domain_for_engagement_metric(self, base_domain, filters):
        parts = [base_domain]

        if filters.get("auditee_id"):
            parts.append([("auditee_id", "=", filters["auditee_id"])])

        if filters.get("auditor_id"):
            parts.append(self._domain_auditor_engagement(filters["auditor_id"]))

        domain = self._safe_and(parts)

        if filters.get("status") or filters.get("severity"):
            Finding = self.env["audit.finding"]
            finding_parts = []

            link_domain = self._domain_finding_engagement_links(filters)
            if link_domain:
                finding_parts.append(link_domain)

            if filters.get("status"):
                finding_parts.append([("status", "=", filters["status"])])

            if filters.get("severity"):
                finding_parts.append([("severity", "=", filters["severity"])])

            finding_domain = self._safe_and(finding_parts)

            try:
                engagement_ids = Finding.search(finding_domain).mapped("engagement_id").ids
            except AccessError:
                raise
            except Exception:
                engagement_ids = []

            domain = self._safe_and([domain, [("id", "in", engagement_ids)]])

        return domain

    @api.model
    def _domain_auditor_corrective_action(self, auditor_id):
        return [
            "|",
            "|",
            "|",
            "|",
            ("action_owner_id", "=", auditor_id),
            ("finding_id.owner_id", "=", auditor_id),
            ("finding_id.responsible_id", "=", auditor_id),
            ("engagement_id.lead_auditor_id", "=", auditor_id),
            ("engagement_id.auditor_ids", "in", [auditor_id]),
        ]

    @api.model
    def _domain_for_corrective_action_metric(self, base_domain, filters):
        parts = [list(base_domain or [])]

        if filters.get("auditee_id"):
            parts.append(
                [("engagement_id.auditee_id", "=", filters["auditee_id"])]
            )

        if filters.get("auditor_id"):
            parts.append(
                self._domain_auditor_corrective_action(filters["auditor_id"])
            )

        if filters.get("status"):
            parts.append([("finding_id.status", "=", filters["status"])])

        if filters.get("severity"):
            parts.append([("finding_id.severity", "=", filters["severity"])])

        return self._safe_and(parts)

    @api.model
    def _domain_for_metric_key(self, metric_key, base_domain, filters):
        spec = DASHBOARD_METRICS.get(metric_key) or {}
        model_name = spec.get("model")

        if model_name == "audit.finding":
            return self._domain_for_finding_metric(base_domain, filters)

        if model_name == "audit.engagement":
            return self._domain_for_engagement_metric(base_domain, filters)

        if model_name == "audit.corrective.action":
            return self._domain_for_corrective_action_metric(base_domain, filters)

        return list(base_domain or [])

    @api.model
    def _count_metric(self, model_name, domain):
        Model = self.env[model_name]
        try:
            return int(Model.search_count(domain))
        except AccessError:
            raise
        except Exception:
            return 0

    @api.model
    def _selection_label(self, model_name, field_name, value):
        Model = self.env[model_name]
        field = Model._fields.get(field_name)

        if not field or field.type != "selection":
            if value in (False, None, ""):
                return _("Unset")
            return str(value)

        selection = field.selection
        if callable(selection):
            selection = selection(Model)

        mapping = dict(selection)
        key = value[0] if isinstance(value, (list, tuple)) and value else value

        if key in (False, None, ""):
            return _("Unset")

        return _(mapping.get(key, str(key)))

    @api.model
    def _read_group_row_count(self, row, group_by_field):
        """Return ``__count`` from an Odoo 20 ``read_group`` tuple.

        Rows are ``(groupby_value, aggregate_value, ...)``. These graphs pass
        one groupby description and the ``__count`` aggregate, so the count is
        the second column. A ``field:granularity`` description is still one column.
        """
        if not group_by_field or not isinstance(row, tuple) or len(row) < 2:
            return 0
        try:
            return int(row[1] or 0)
        except (TypeError, ValueError):
            return 0

    @api.model
    def _graph_from_read_group(self, model_name, domain, group_by_field):
        Model = self.env[model_name]
        field_name = group_by_field.split(":", 1)[0]
        field = Model._fields.get(field_name)

        if not field:
            return [], []

        try:
            groups = Model.read_group(
                domain,
                [group_by_field],
                ["__count"],
            )
        except AccessError:
            raise
        except Exception:
            return [], []

        labels = []
        values = []

        for row in groups:
            count = self._read_group_row_count(row, group_by_field)
            raw = row[0] if row else False

            if field.type == "many2one":
                record_id = self._many2one_raw_id(raw)
                if record_id:
                    record = self.env[field.comodel_name].browse(record_id)
                    labels.append(
                        record.display_name if record.exists() else _("Unset")
                    )
                else:
                    labels.append(_("Unset"))

            elif field.type == "selection":
                labels.append(self._selection_label(model_name, group_by_field, raw))

            elif field.type == "date":
                labels.append(str(raw) if raw else _("Unset"))

            else:
                labels.append(str(raw) if raw is not False else _("Unset"))

            values.append(count)

        return labels, values

    @api.model
    def _graph_critical_by_auditee(self, domain):
        Finding = self.env["audit.finding"]
        Engagement = self.env["audit.engagement"]
        Partner = self.env["res.partner"]

        try:
            groups = Finding.read_group(
                domain,
                ["engagement_id"],
                ["__count"],
            )
        except AccessError:
            raise
        except Exception:
            return [], []

        totals = defaultdict(int)

        for row in groups:
            count = self._read_group_row_count(row, "engagement_id")
            engagement_id = self._many2one_raw_id(row[0] if row else False)

            if not engagement_id:
                totals[False] += count
                continue

            engagement = Engagement.browse(engagement_id)
            auditee = engagement.auditee_id if engagement.exists() else False
            totals[auditee.id if auditee else False] += count

        def _sort_key(partner_id):
            if not partner_id:
                return (1, "")
            partner = Partner.browse(partner_id)
            return (0, partner.display_name or "")

        labels = []
        values = []

        for partner_id in sorted(totals.keys(), key=_sort_key):
            if not partner_id:
                labels.append(_("Unset auditee"))
            else:
                partner = Partner.browse(partner_id)
                labels.append(partner.display_name or str(partner_id))
            values.append(totals[partner_id])

        return labels, values

    @api.model
    def _check_dashboard_access(self):
        """Model-level read check for this service (empty recordset)."""
        self.browse().check_access("read")

    @api.model
    def get_dashboard_summary(self, filters=None):
        self._check_dashboard_access()
        norm = self._normalize_dashboard_filters(filters)
        result = {}

        for key, spec in DASHBOARD_METRICS.items():
            model_name = spec.get("model")
            base_domain = list(spec.get("domain") or [])
            aggregation = spec.get("aggregation")

            if not model_name or aggregation != "count":
                result[key] = 0
                continue

            domain = self._domain_for_metric_key(key, base_domain, norm)
            result[key] = self._count_metric(model_name, domain)

        capa_base = self._domain_for_corrective_action_metric([], norm)
        capa_total_n = self._count_metric("audit.corrective.action", capa_base)
        capa_done_n = self._count_metric(
            "audit.corrective.action",
            self._safe_and([capa_base, [("state", "=", "done")]]),
        )
        if capa_total_n:
            result["capa_completion_rate"] = int(
                round(100.0 * capa_done_n / float(capa_total_n))
            )
        else:
            result["capa_completion_rate"] = 0

        return result

    @api.model
    def get_dashboard_graph_data(self, metric_key, filters=None):
        self._check_dashboard_access()
        if metric_key == "capa_completion_rate":
            metric_key = "capa_total"

        spec = DASHBOARD_METRICS.get(metric_key)

        if not spec:
            return {"labels": [], "values": []}

        norm = self._normalize_dashboard_filters(filters)
        model_name = spec.get("model")
        base_domain = list(spec.get("domain") or [])
        domain = self._domain_for_metric_key(metric_key, base_domain, norm)
        group_by = spec.get("group_by")
        graph_scope = spec.get("graph_scope")

        if graph_scope == "critical_by_auditee":
            labels, values = self._graph_critical_by_auditee(domain)
            return {"labels": labels, "values": values}

        if group_by:
            labels, values = self._graph_from_read_group(model_name, domain, group_by)
            return {"labels": labels, "values": values}

        total = self._count_metric(model_name, domain)
        return {"labels": [_("Value")], "values": [total]}

    @api.model
    def get_dashboard_filters_data(self):
        self._check_dashboard_access()
        Engagement = self.env["audit.engagement"]
        Finding = self.env["audit.finding"]
        Users = self.env["res.users"]
        Partner = self.env["res.partner"]

        auditor_ids = set()
        try:
            for engagement in Engagement.search([]):
                if engagement.lead_auditor_id:
                    auditor_ids.add(engagement.lead_auditor_id.id)
                auditor_ids.update(engagement.auditor_ids.ids)

            for finding in Finding.search([]):
                if finding.owner_id:
                    auditor_ids.add(finding.owner_id.id)
                if finding.responsible_id:
                    auditor_ids.add(finding.responsible_id.id)
        except AccessError:
            raise
        except Exception:
            auditor_ids = set()

        auditors = []
        for user in Users.browse(sorted(auditor_ids)):
            if user.exists():
                auditors.append({"id": user.id, "name": user.name or ""})

        auditee_ids = set()
        try:
            for engagement in Engagement.search([]):
                if engagement.auditee_id:
                    auditee_ids.add(engagement.auditee_id.id)
        except AccessError:
            raise
        except Exception:
            auditee_ids = set()

        auditees = []
        for partner in Partner.browse(sorted(auditee_ids)):
            if partner.exists():
                auditees.append({"id": partner.id, "name": partner.display_name or ""})

        FindingModel = self.env["audit.finding"]

        statuses = []
        status_field = FindingModel._fields.get("status")
        if status_field and status_field.type == "selection":
            selection = status_field.selection
            if callable(selection):
                selection = selection(FindingModel)
            statuses = [key for key, _label in selection]

        severities = []
        severity_field = FindingModel._fields.get("severity")
        if severity_field and severity_field.type == "selection":
            selection = severity_field.selection
            if callable(selection):
                selection = selection(FindingModel)
            severities = [key for key, _label in selection]

        return {
            "auditors": auditors,
            "auditees": auditees,
            "statuses": statuses,
            "severities": severities,
        }