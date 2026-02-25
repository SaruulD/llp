from odoo import api, models

class ReportPayrollMatrix(models.AbstractModel):
    _name = 'report.llp_payroll.report_payroll_matrix_pdf'
    _description = 'Payroll Matrix PDF Report'

    @api.model
    def _get_report_values(self, docids, data=None):
        wizard = self.env['llp.payroll.salary.report'].browse(docids)  # change to your wizard model
        wizard.ensure_one()
        vals = wizard._get_report_data()
        return {
            'doc_ids': docids,
            'doc_model': wizard._name,
            'docs': wizard,
            'vals': vals,
        }