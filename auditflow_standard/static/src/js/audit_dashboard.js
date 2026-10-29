/** @odoo-module **/
import { Component, onWillStart, proxy, useProps } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { _t, translationIsReady } from "@web/core/l10n/translation";
import { useService } from "@web/core/utils/hooks";
import { standardActionServiceProps } from "@web/webclient/actions/action_plugin";


// Translation anchors for Odoo extraction/runtime 
_t("Executive Dashboard"); 
_t("Real-time insights for internal audit"); 
_t("Total engagements"); 
_t("Open review results"); 
_t("Critical review results"); 
_t("Overdue review results"); 
_t("Completed engagements");
_t("Risk level"); 
_t("Update");


const CHART_TYPES = {
    total_engagements: "bar",
    open_findings: "bar",
    critical_findings: "bar",
    overdue_findings: "line",
    completed_engagements: "bar",
    risk_exposure: "donut",
    capa_total: "bar",
    capa_open: "bar",
    capa_overdue: "bar",
    capa_completed: "bar",
    capa_high_risk_open: "donut",
    capa_completion_rate: "donut",
};

const DONUT_COLORS = ["#2563EB", "#1E3A8A", "#0F172A", "#34D399", "#F97316", "#93C5FD"];

const EMPTY_FILTERS = {
    auditor_id: "",
    auditee_id: "",
    status: "",
    severity: "",
};

export class AuditDashboard extends Component {
    static template = "auditflow_standard.AuditDashboard";
    props = useProps({
        ...standardActionServiceProps,
    });

    setup() {
        this.orm = useService("orm");
        this.state = proxy({
            loading: true,
            errorKey: null,
            summary: {},
            selectedMetric: "total_engagements",
            graphLoading: false,
            graphErrorKey: null,
            graphData: { labels: [], values: [] },
            filtersLoading: false,
            filtersData: {
                auditors: [],
                auditees: [],
                statuses: [],
                severities: [],
            },
            activeFilters: { ...EMPTY_FILTERS },
            dashboardRefreshing: false,
        });

        onWillStart(async () => {
            await translationIsReady;
            try {
                await this.fetchSummaryAndChart();
                this.state.loading = false;
                await this.loadFiltersData();
            } catch (_error) {
                this.state.errorKey = "load_dashboard";
                this.state.loading = false;
            }
        });
    }

    _selectionLabel(key) {
        const labels = {
            open: _t("Open"),
            in_review: _t("In Review"),
            closed: _t("Closed"),
            done: _t("Done"),
            cancelled: _t("Cancelled"),
            low: _t("Low"),
            medium: _t("Medium"),
            high: _t("High"),
            critical: _t("Critical"),
            high_risk: _t("High Risk"),
            in_progress: _t("In Progress"),
            draft: _t("Draft"),
            assigned: _t("Assigned"),
            no_action: _t("No action"),
            pending: _t("Pending action"),
            overdue: _t("Delayed"),
            completed: _t("Completed"),
            fieldwork: _t("Fieldwork"),
            reporting: _t("Reporting"),
            issued: _t("Issued"),
            ready: _t("Ready"),
            not_ready: _t("Not Ready"),
            control_design: _t("Control Design"),
            control_operational: _t("Control Operational"),
            compliance: _t("Compliance"),
            risk: _t("Risk"),
        };
        return labels[key];
    }

    formatSelectionDisplay(key) {
        if (key === undefined || key === null || key === "") {
            return "";
        }
        const k = String(key);
        const mapped = this._selectionLabel(k);
        if (mapped) {
            return mapped;
        }
        const s = k.replace(/_/g, " ");
        return s.replace(/\w\S*/g, (txt) =>
            txt.charAt(0).toUpperCase() + txt.slice(1).toLowerCase()
        );
    }

    get dashboardTexts() {
        return {
            pageTitle: _t("Executive Dashboard"),
            pageSubtitle: _t("Real-time insights for internal audit"),
            badgeMvp: _t("Standard analytics"),
            filterAuditor: _t("Reviewer"),
            filterAuditee: _t("Entity under review"),
            filterStatus: _t("Execution status"),
            allStatuses: _t("All execution statuses"),
            allSeverities: _t("All Severities"),
            filterSeverity: _t("Risk level"),
            allAuditors: _t("All reviewers"),
            allAuditees: _t("All entities under review"),
            refresh: _t("Refresh"),
            filtersHint: _t(
                "Filters apply to KPI totals and the selected metric chart."
            ),
            bannerRefreshing: _t("Refreshing dashboard..."),
            loadingDashboard: _t("Loading dashboard data..."),
            loadingChart: _t("Loading chart data..."),
            noChartData: _t("No chart data available."),
            headingSelectedMetric: _t("Selected metric"),
            technicalKeyCaption: _t("Technical key"),
            donutTotal: _t("Total"),
            insightTitle: _t("Executive insight"),
            insightMetric: _t("Metric"),
            insightChartTotal: _t("Chart total"),
            insightChartType: _t("Chart type"),
            insightBody: _t(
                "Use this view to identify internal audit pressure points and prioritize management attention."
            ),
            powerBiTitle: _t("External reporting"),
            powerBiBadge: _t("Placeholder"),
            powerBiBody: _t(
                "Reserve this panel for links to management reports or an external analytics tool if your organization adds one later."
            ),
            comingSoon: _t("Coming soon"),
        };
    }

    get errorMessage() {
        const messages = {
            load_dashboard: _t("Could not load dashboard data."),
            refresh_dashboard: _t("Could not refresh dashboard data."),
        };
        return this.state.errorKey
            ? messages[this.state.errorKey] || this.state.errorKey
            : null;
    }

    get graphErrorMessage() {
        if (this.state.graphErrorKey === "load_chart") {
            return _t("Could not load chart data.");
        }
        return null;
    }

    get activeFilters() {
        return this.state.activeFilters || { ...EMPTY_FILTERS };
    }

    getRpcFilters() {
        const f = this.activeFilters;
        const parseId = (raw) => {
            if (raw === undefined || raw === null || raw === "") {
                return false;
            }
            const n = parseInt(String(raw), 10);
            return Number.isFinite(n) && n > 0 ? n : false;
        };

        return {
            auditor_id: parseId(f.auditor_id),
            auditee_id: parseId(f.auditee_id),
            status: f.status ? String(f.status) : false,
            severity: f.severity ? String(f.severity) : false,
        };
    }

    async fetchSummaryAndChart() {
        const filters = this.getRpcFilters();
        const summary = await this.orm.call(
            "audit.dashboard.service",
            "get_dashboard_summary",
            [filters]
        );
        this.state.summary = summary || {};
        await this.loadGraphData(this.state.selectedMetric);
    }

    async loadFiltersData() {
        this.state.filtersLoading = true;
        try {
            const data = await this.orm.call(
                "audit.dashboard.service",
                "get_dashboard_filters_data",
                []
            );
            this.state.filtersData = {
                auditors: data?.auditors || [],
                auditees: data?.auditees || [],
                statuses: data?.statuses || [],
                severities: data?.severities || [],
            };
        } catch (_error) {
            this.state.filtersData = {
                auditors: [],
                auditees: [],
                statuses: [],
                severities: [],
            };
        } finally {
            this.state.filtersLoading = false;
        }
    }

    async refreshDashboard(options = {}) {
        const reloadFilters = options.reloadFilters !== false;
        if (this.state.dashboardRefreshing) {
            return;
        }

        this.state.dashboardRefreshing = true;
        this.state.errorKey = null;

        try {
            await this.fetchSummaryAndChart();
            if (reloadFilters) {
                await this.loadFiltersData();
            }
        } catch (_error) {
            this.state.errorKey = "refresh_dashboard";
        } finally {
            this.state.dashboardRefreshing = false;
        }
    }

    onFilterChange(filterKey, value) {
        this.state.activeFilters = {
            ...this.activeFilters,
            [filterKey]: value || "",
        };
        void this.refreshDashboard({ reloadFilters: false });
    }

    translateChartRowLabel(raw) {
        const label = raw == null ? "" : String(raw).trim();

        if (!label) {
            return _t("Unset");
        }

        const normalized = label.toLowerCase().replace(/\s+/g, "_");
        const mappedSelection = this._selectionLabel(normalized);
        if (mappedSelection) {
            return mappedSelection;
        }

        const stableLabels = {
            unset: _t("Unset"),
            unset_auditee: _t("Unset auditee"),
            value: _t("Value"),
            total: _t("Total"),
            distribution: _t("Distribution"),
            trend: _t("Trend"),
            bar_chart: _t("Bar Chart"),
            high_risk: _t("High Risk"),
            in_progress: _t("In Progress"),
        };

        return stableLabels[normalized] || label;
    }

    get statusFilterOptions() {
        const keys = this.state.filtersData?.statuses || [];
        return keys.map((value) => ({
            value,
            label: this.formatSelectionDisplay(value),
        }));
    }

    get severityFilterOptions() {
        const keys = this.state.filtersData?.severities || [];
        return keys.map((value) => ({
            value,
            label: this.formatSelectionDisplay(value),
        }));
    }

    async loadGraphData(metricKey) {
        this.state.graphLoading = true;
        this.state.graphErrorKey = null;

        try {
            const filters = this.getRpcFilters();
            const data = await this.orm.call(
                "audit.dashboard.service",
                "get_dashboard_graph_data",
                [metricKey, filters]
            );
            this.state.graphData = {
                labels: data?.labels || [],
                values: data?.values || [],
            };
        } catch (_error) {
            this.state.graphErrorKey = "load_chart";
            this.state.graphData = { labels: [], values: [] };
        } finally {
            this.state.graphLoading = false;
        }
    }

    selectMetric(metricKey) {
        if (this.state.selectedMetric === metricKey) {
            return;
        }
        this.state.selectedMetric = metricKey;
        void this.loadGraphData(metricKey);
    }

    kpiValue(key) {
        const v = this.state.summary?.[key];
        if (key === "capa_completion_rate") {
            if (v === undefined || v === null) {
                return "0%";
            }
            const n = typeof v === "number" ? v : Number(v) || 0;
            return `${n}%`;
        }
        if (v === undefined || v === null) {
            return 0;
        }
        return typeof v === "number" ? v : Number(v) || 0;
    }

    get metricCards() {
        return [
            {
                key: "total_engagements",
                label: _t("Total engagements"),
                icon: "fa fa-clipboard-list",
                tone: "primary",
            },
            {
                key: "open_findings",
                label: _t("Open review results"),
                icon: "fa fa-folder-open",
                tone: "info",
            },
            {
                key: "critical_findings",
                label: _t("Critical review results"),
                icon: "fa fa-exclamation-triangle",
                tone: "danger",
            },
            {
                key: "overdue_findings",
                label: _t("Overdue review results"),
                icon: "fa fa-clock-o",
                tone: "warning",
            },
            {
                key: "completed_engagements",
                label: _t("Completed engagements"),
                icon: "fa fa-check-circle",
                tone: "success",
            },
            {
                key: "risk_exposure",
                label: _t("Risk level"),
                icon: "fa fa-shield",
                tone: "dark",
            },
            {
                key: "capa_total",
                label: _t("Total Corrective Actions (CAPA)"),
                icon: "fa fa-tasks",
                tone: "primary",
            },
            {
                key: "capa_open",
                label: _t("Open Corrective Actions (CAPA)"),
                icon: "fa fa-folder-open",
                tone: "info",
            },
            {
                key: "capa_overdue",
                label: _t("Delayed Corrective Actions (CAPA)"),
                icon: "fa fa-clock-o",
                tone: "danger",
            },
            {
                key: "capa_completed",
                label: _t("Completed Corrective Actions (CAPA)"),
                icon: "fa fa-check-circle",
                tone: "success",
            },
            {
                key: "capa_completion_rate",
                label: _t("Corrective Action (CAPA) completion rate"),
                icon: "fa fa-percent",
                tone: "dark",
            },
            {
                key: "capa_high_risk_open",
                label: _t("High-risk open Corrective Actions (CAPA)"),
                icon: "fa fa-exclamation-circle",
                tone: "warning",
            },
        ];
    }

    get selectedMetricLabel() {
        const card = this.metricCards.find(
            (c) => c.key === this.state.selectedMetric
        );
        return card ? card.label : _t("Metric");
    }

    get chartType() {
        return CHART_TYPES[this.state.selectedMetric] || "bar";
    }

    get chartTypeLabel() {
        const labels = {
            bar: _t("Bar Chart"),
            line: _t("Trend"),
            donut: _t("Distribution"),
        };
        return labels[this.chartType] || _t("Bar Chart");
    }

    get graphRows() {
        const labels = this.state.graphData?.labels || [];
        const values = this.state.graphData?.values || [];
        const nums = labels.map((_, i) => Number(values[i] || 0));
        const max = Math.max(1, ...nums);

        return labels.map((label, index) => {
            const value = nums[index];
            return {
                label: this.translateChartRowLabel(label),
                value,
                percent: Math.round((value / max) * 100),
            };
        });
    }

    get graphTotal() {
        return (this.state.graphData?.values || []).reduce(
            (sum, value) => sum + (Number(value) || 0),
            0
        );
    }

    get graphRowCount() {
        return this.graphRows.length;
    }

    get donutRingGradient() {
        const labels = this.state.graphData?.labels || [];
        const values = (this.state.graphData?.values || []).map((v) =>
            Number(v || 0)
        );
        const total = values.reduce((a, b) => a + b, 0);

        if (!total || !labels.length) {
            return "conic-gradient(#dee2e6 0deg 360deg)";
        }

        const colors = DONUT_COLORS;

        let angle = 0;
        const parts = [];

        labels.forEach((_, i) => {
            const val = values[i] || 0;
            const deg = (val / total) * 360;
            const color = colors[i % colors.length];

            if (deg > 0) {
                parts.push(`${color} ${angle}deg ${angle + deg}deg`);
            }

            angle += deg;
        });

        return `conic-gradient(${parts.join(", ")})`;
    }

    get donutRingStyleAttr() {
        return `background-image: ${this.donutRingGradient}`;
    }

    donutSliceColor(rowIndex) {
        const index = Number(rowIndex) || 0;
        return DONUT_COLORS[index % DONUT_COLORS.length];
    }

    donutSlicePercent(rowIndex) {
        const total = this.graphTotal;
        const values = this.state.graphData?.values || [];
        const v = Number(values[rowIndex] || 0);

        if (!total || !v) {
            return 0;
        }

        return Math.round((v / total) * 100);
    }

    cardClass(card) {
        const active =
            this.state.selectedMetric === card.key ? " is-active" : "";
        return `o_audit_kpi_card audit-kpi-card dashboard-kpi-card tone-${card.tone}${active}`;
    }
}

registry.category("actions").add("auditflow_dashboard", AuditDashboard);
