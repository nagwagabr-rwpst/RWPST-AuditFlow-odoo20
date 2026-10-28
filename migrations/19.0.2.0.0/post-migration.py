"""Phase-1 post-migration hook.

Backfills the new company_id columns on audit_plan_stable / audit_task_stable /
audit_indicator_stable so existing records are not hidden by the new multi-company
record rule after upgrade.

Order of operations in Odoo's upgrade pipeline:
  1. Schema upgrade adds the new company_id column (Python default fires).
  2. Updated XML data is loaded.
  3. This post-migration runs.

After step 1 the column is usually already non-NULL for plans, but two cases
remain for tasks/indicators:

  a) Rows with a NULL plan_id cannot inherit a company from their parent.
     Their stored compute (in 19.0.2.0.0) falls back to env.company, but we
     also defensively backfill here in case the compute has not yet run.

  b) Rows whose company_id drifted from their plan's company_id - sync them.

Runs only on upgrade (Odoo passes version='' on fresh install).
"""
import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        return

    cr.execute("SELECT id FROM res_company ORDER BY id LIMIT 1")
    row = cr.fetchone()
    if not row:
        _logger.warning("smart_audit: no company found, skipping backfill")
        return
    main_company_id = row[0]

    # --- 1. Plans: adopt main company when null. --------------------------
    cr.execute(
        """
        UPDATE audit_plan_stable
           SET company_id = %s
         WHERE company_id IS NULL
        """,
        (main_company_id,),
    )
    _logger.info(
        "smart_audit: backfilled company_id on audit_plan_stable (%s rows)",
        cr.rowcount,
    )

    # --- 2. Tasks: inherit from plan, fallback to main company. -----------
    cr.execute(
        """
        UPDATE audit_task_stable t
           SET company_id = p.company_id
          FROM audit_plan_stable p
         WHERE t.plan_id = p.id
           AND t.company_id IS DISTINCT FROM p.company_id
        """
    )
    _logger.info(
        "smart_audit: synced company_id on audit_task_stable from parent plan (%s rows)",
        cr.rowcount,
    )

    # Orphan tasks (plan_id IS NULL) would otherwise remain NULL and be
    # hidden by the global multi-company rule. Assign them to main company.
    cr.execute(
        """
        UPDATE audit_task_stable
           SET company_id = %s
         WHERE company_id IS NULL
        """,
        (main_company_id,),
    )
    _logger.info(
        "smart_audit: backfilled orphan company_id on audit_task_stable (%s rows)",
        cr.rowcount,
    )

    # --- 3. Indicators: same pattern as tasks. ----------------------------
    cr.execute(
        """
        UPDATE audit_indicator_stable i
           SET company_id = p.company_id
          FROM audit_plan_stable p
         WHERE i.plan_id = p.id
           AND i.company_id IS DISTINCT FROM p.company_id
        """
    )
    _logger.info(
        "smart_audit: synced company_id on audit_indicator_stable from parent plan (%s rows)",
        cr.rowcount,
    )

    cr.execute(
        """
        UPDATE audit_indicator_stable
           SET company_id = %s
         WHERE company_id IS NULL
        """,
        (main_company_id,),
    )
    _logger.info(
        "smart_audit: backfilled orphan company_id on audit_indicator_stable (%s rows)",
        cr.rowcount,
    )
