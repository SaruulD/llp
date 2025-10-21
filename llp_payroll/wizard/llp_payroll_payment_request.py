from odoo import api, fields, models, _
from datetime import date
import calendar

class LLPPayrollPaymentRequest(models.TransientModel):
    _name = 'llp.payroll.payment.request'
    _description = 'Payroll Payment Request Wizard'

    # ── Read-only, auto-filled from context ────────────────────────────────────
    salary_bank_type = fields.Char(string="Цалин авах банк/төрөл", readonly=True)
    payment_ref = fields.Char(string="Гүйлгээний утга", readonly=True)
    amount = fields.Monetary(string="Гүйлгээний дүн", readonly=True)
    currency_id = fields.Many2one(
        'res.currency',
        string="Валют",
        default=lambda self: self.env.company.currency_id.id,
        readonly=True
    )

    # ── Required user inputs ───────────────────────────────────────────────────
    partner_id = fields.Many2one(
        'res.partner',
        string="Хүлээн авах харилцагч",
        required=True
    )
    partner_bank_id = fields.Many2one(
        'res.partner.bank',
        string="Хүлээн авах банкны данс",
        required=True,
        domain="[('partner_id', '=', partner_id)]"
    )
    journal_id = fields.Many2one(
        'account.journal',
        string="Гүйлгээ гарах журнал",
        required=True,
        domain="[('type', '=', 'bank'), ('company_id', '=', company_id)]"
    )

    # ── Auto from selected journal (read-only) ────────────────────────────────
    journal_bank_account_id = fields.Many2one(
        'res.partner.bank',
        string="Банкны данс",
        related='journal_id.bank_account_id',
        readonly=True
    )

    # helpers
    company_id = fields.Many2one(
        'res.company',
        default=lambda self: self.env.company.id,
        readonly=True
    )

    # Populate defaults based on context coming from the button
    @api.model
    def default_get(self, fields_list):
        vals = super().default_get(fields_list)

        # Expected context keys (set in the button action):
        # payroll_type: 'advance' | 'month_end'
        # payroll_month: date or string like '2025-08-01'
        # salary_type_name: str
        # amount: float
        # currency_id: int (optional)
        ctx = self.env.context

        payroll_type = ctx.get('payroll_type')            # 'advance' or 'month_end'
        payroll_month = ctx.get('payroll_month')          # date or string
        salary_type_name = ctx.get('salary_type_name')    # e.g., "Сарын сүүл"
        amount = ctx.get('amount')                        # batched amount
        currency_id = ctx.get('currency_id') or self.env.company.currency_id.id

        # 1) Цалин авах банк/төрөл
        if 'salary_bank_type' in fields_list:
            vals['salary_bank_type'] = salary_type_name or ''

        # 2) Гүйлгээний утга
        month_label = ''
        if payroll_month:
            if isinstance(payroll_month, str):
                # attempt to parse YYYY-MM-DD
                try:
                    y, m, d = payroll_month.split('-')
                    month_label = f"{int(m)}"
                except Exception:
                    month_label = str(payroll_month)
            elif isinstance(payroll_month, date):
                month_label = f"{payroll_month.month}"
        if not month_label:
            # fallback to current month
            month_label = str(fields.Date.context_today(self).month)

        if 'payment_ref' in fields_list:
            if payroll_type == 'advance':
                vals['payment_ref'] = _("%s сарын урьдчилгаа цалин") % month_label
            else:
                vals['payment_ref'] = _("%s сарын сүүл цалин") % month_label

        # 3) Гүйлгээний дүн (readonly)
        if 'amount' in fields_list:
            vals['amount'] = amount or 0.0

        if 'currency_id' in fields_list:
            vals['currency_id'] = currency_id

        return vals

    # Optional: finalize action when user confirms (replace with real logic)
    def action_confirm(self):
        self.ensure_one()
        # Implement your payment request creation here (e.g., create a payment record or draft)
        # Example: post a message on the originating record if context provides it
        origin_model = self.env.context.get('active_model')
        origin_id = self.env.context.get('active_id')
        if origin_model and origin_id:
            rec = self.env[origin_model].browse(origin_id)
            rec.message_post(body=_(
                "Цалингийн төлбөрийн хүсэлт баталгаажлаа:<br/>"
                "Банк/төрөл: %s<br/>"
                "Гүйлгээний утга: %s<br/>"
                "Дүн: %s<br/>"
                "Хүлээн авагч: %s<br/>"
                "Хүлээн авах данс: %s<br/>"
                "Журнал: %s<br/>"
                "Гарах данс: %s"
            ) % (
                self.salary_bank_type or '',
                self.payment_ref or '',
                f"{self.amount:,.2f}",
                self.partner_id.display_name,
                self.partner_bank_id.acc_number or '',
                self.journal_id.display_name,
                self.journal_bank_account_id.acc_number or ''
            ))
        return {'type': 'ir.actions.act_window_close'}
