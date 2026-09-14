# -*- coding: utf-8 -*-
from odoo import api, fields, models, _ # type: ignore
from odoo.exceptions import UserError # type: ignore
from odoo.tools import exception_to_unicode # type: ignore
from operator import itemgetter


class LLPPayrollAccountMove(models.TransientModel):
    _name = 'llp.payroll.account.move'
    _description = 'Payroll Account Move Wizard'

    line_ids = fields.One2many('llp.payroll.account.move.line', 'account_move_line_id', string="Lines")

    # ------------------------------------------------------------------
    # Ажилтныг unit-тэй тааруулах
    # ------------------------------------------------------------------
    def _get_employee_unit(self, payroll_id, employee):
        """Ажилтны бодит department_id-аар нь (company-аар шүүж) llp.payroll.unit
        хайна. Олдвол (department, unit) буцаана. Олдохгүй бол
        department_ids сонгоогүй ерөнхий unit-ийг company-аар нь хайж,
        (хоосон department, unit) буцаана."""
        Unit = self.env['llp.payroll.unit']
        dept = employee.department_id
        if dept:
            unit = Unit.search([
                ('company_id', '=', payroll_id.company_id.id),
                ('department_ids', 'in', dept.ids),
            ], limit=1)
            if unit:
                return dept, unit
        fallback_unit = Unit.search([
            ('company_id', '=', payroll_id.company_id.id),
            ('department_ids', '=', False),
        ], limit=1)
        return self.env['hr.department'], fallback_unit

    def _group_employees_by_unit(self, payroll_id, raise_if_missing=False):
        """payroll_id.line_ids-ийг тохирох unit-ээр нь бүлэглэнэ.
        Буцаах утга: [{'department': hr.department, 'unit': llp.payroll.unit,
        'lines': [llp.payroll.line, ...]}, ...]"""
        groups = {}
        for obj in payroll_id.line_ids:
            line = obj.sudo()
            department, unit = self._get_employee_unit(payroll_id, line.employee_id)
            if not unit:
                if raise_if_missing:
                    raise UserError(_(
                        u'%s ажилтны алба нэгжид тохирох журналын тохиргоо '
                        u'(llp.payroll.unit) олдсонгүй. Мөн "алба нэгж '
                        u'сонгоогүй" ерөнхий тохиргоо ч алга байна.'
                    ) % line.employee_id.name)
                continue
            key = unit.id
            if key not in groups:
                groups[key] = {'department': department, 'unit': unit, 'lines': []}
            groups[key]['lines'].append(line)
        return list(groups.values())

    @api.model
    def default_get(self, fields):
        res = super(LLPPayrollAccountMove, self).default_get(fields)
        payroll_id = self.env['llp.payroll'].browse(self._context.get('active_ids', []))

        moves = []
        for group in self._group_employees_by_unit(payroll_id):
            moves += self._compute_unit_preview_lines(
                payroll_id, group['department'], group['unit'], group['lines']
            )

        for idx, move in enumerate(moves, start=1):
            move[2]['no'] = idx

        if moves:
            res.update({'line_ids': moves})

        return res

    def _compute_unit_preview_lines(self, payroll_id, department, unit, emp_lines):
        """Нэг unit-т харьяалагдах ажилтны мөрүүдээс урьдчилан харуулах
        llp.payroll.account.move.line-ийн (0,0,vals) tuple-үүдийг үүсгэнэ."""
        move_lines = {}
        debt_debit_account_id = False
        debt_credit_account_id = False
        moves = []
        dbamount = 0.0

        for obj in unit.line_ids:
            uline = obj.sudo()
            if uline.rule_id.transaction_type == 'by_partner':
                debt_debit_account_id = uline.debit_account_id.id if uline.debit_account_id else False
                debt_credit_account_id = uline.credit_account_id.id if uline.credit_account_id else False
            elif uline.rule_id.id not in move_lines:
                move_lines[uline.rule_id.id] = {
                    'rule': uline.rule_id.id,
                    'debit_sum': 0.0,
                    'credit_sum': 0.0,
                    'debit_account_id': uline.debit_account_id.id if uline.debit_account_id else False,
                    'credit_account_id': uline.credit_account_id.id if uline.credit_account_id else False,
                    'internal_type': False,
                    'note': uline.transaction_value,
                    'partners': {},
                }

        for line in emp_lines:
            cramount = 0.0
            for rule in line.rule_value_ids:
                if rule.payroll_rule_id.id in move_lines:
                    move_lines[rule.payroll_rule_id.id]['debit_sum'] += round(rule.value, 2)
                    move_lines[rule.payroll_rule_id.id]['credit_sum'] += round(rule.value, 2)

                    if round(rule.value, 2) != 0.0:
                        group_partner = line.employee_id.work_contact_id.id
                        partners = move_lines[rule.payroll_rule_id.id]['partners']
                        if group_partner not in partners:
                            partners[group_partner] = {'amount': 0.0, 'partner_id': False, 'name': ''}
                        partners[group_partner]['amount'] += round(rule.value, 2)
                        partners[group_partner]['partner_id'] = group_partner
                        partners[group_partner]['name'] = u'[%s - [%s]' % (
                            move_lines[rule.payroll_rule_id.id]['note'], line.employee_id.name)

                if rule.payroll_rule_id.transaction_type == 'by_partner':
                    cramount += round(rule.value, 2)

            if round(cramount, 2) != 0.0:
                dbamount += round(cramount, 2)
                moves.append((0, 0, {
                    'name': u'[Цалин харилцагчаар задлах - [%s]' % (line.employee_id.name),
                    'debit': 0.0,
                    'credit': round(cramount, 2),
                    'account_id': debt_credit_account_id,
                    'amount_currency': 0.0,
                    'department_id': department.id if department else False,
                    'journal_id': unit.journal_id.id,
                }))

        if round(dbamount, 2) != 0.0:
            moves.append((0, 0, {
                'name': u'[Цалин харилцагчаар задлах - %s]' % (department.name if department else unit.name),
                'debit': round(dbamount, 2),
                'credit': 0.0,
                'account_id': debt_debit_account_id,
                'amount_currency': 0.0,
                'department_id': department.id if department else False,
                'journal_id': unit.journal_id.id,
            }))

        for move in sorted(move_lines.values(), key=itemgetter('rule')):
            if move['debit_sum'] != 0.0 and move['credit_sum'] != 0.0:
                moves += self.defaut_get_create_move(move, department, unit)

        return moves

    def defaut_get_create_move(self, move, department, unit):
        moves = []
        dept_id = department.id if department else False
        journal_id = unit.journal_id.id

        if move['internal_type'] == 'credit' or not move['internal_type']:
            moves.append((0, 0, {
                'name': u'[Цалин] %s' % (move['note']),
                'debit': round(move['debit_sum'], 2) > 0 and round(move['debit_sum'], 2),
                'credit': round(move['debit_sum'], 2) < 0 and -1 * round(move['debit_sum'], 2),
                'account_id': move['debit_account_id'],
                'amount_currency': 0.0,
                'department_id': dept_id,
                'journal_id': journal_id,
            }))

        # Credit
        if move['internal_type'] == 'debit' or not move['internal_type']:
            moves.append((0, 0, {
                'name': u'[Цалин] %s' % (move['note']),
                'debit': round(move['debit_sum'], 2) < 0 and -1 * round(move['debit_sum'], 2),
                'credit': round(move['credit_sum'], 2) > 0 and round(move['credit_sum'], 2),
                'account_id': move['credit_account_id'],
                'amount_currency': 0.0,
                'department_id': dept_id,
                'journal_id': journal_id,
            }))

        if move['internal_type']:
            for part in sorted(move['partners'].values(), key=itemgetter('partner_id')):
                amount = round(part['amount'], 2) > 0 and round(part['amount'], 2) or -1 * round(part['amount'], 2)
                account = move['internal_type'] == 'debit' and move['debit_account_id'] or move['credit_account_id']
                moves.append((0, 0, {
                    'name': part['name'],
                    'debit': move['internal_type'] == 'debit' and amount or 0.0,
                    'credit': move['internal_type'] == 'credit' and amount or 0.0,
                    'account_id': account,
                    'amount_currency': 0.0,
                    'department_id': dept_id,
                    'journal_id': journal_id,
                }))
        return moves

    # ------------------------------------------------------------------
    # action_confirm — бодит account.move үүсгэх
    # ------------------------------------------------------------------
    def clear_previous_moves_and_history(self, payroll_id):
        if not payroll_id or not payroll_id.payment_history_ids:
            return
        for his in payroll_id.payment_history_ids:
            if his.move_id:
                his.move_id.button_draft()
                his.unlink()
                self.env.cr.commit()

    def action_confirm(self):
        self.ensure_one()
        payroll_id = self.env['llp.payroll'].browse(self._context.get('active_ids', []))

        groups = self._group_employees_by_unit(payroll_id, raise_if_missing=True)
        for group in groups:
            if not group['unit'].line_ids:
                raise UserError(_(
                    u'"%s" (%s) - д журналын бичилтын тохиргоо хийгдээгүй байна!!!'
                ) % (
                    group['unit'].name or group['unit'].code or group['unit'].id,
                    group['department'].name if group['department'] else _(u'Алба нэгж сонгоогүй'),
                ))

        self.clear_previous_moves_and_history(payroll_id)

        mmoves = []
        for group in groups:
            self._create_unit_account_moves(
                payroll_id, group['department'], group['unit'], group['lines'], mmoves
            )

        self.env.cr.commit()
        return True

    def _create_unit_account_moves(self, payroll_id, department, unit, emp_lines, mmoves):
        """emp_lines-д багтсан ажилтнуудын дүнгээр, unit.journal_id дээр
        нэг буюу хэд хэдэн account.move үүсгэнэ. Амжилттай үүссэн бүх
        move-ийн id-г mmoves жагсаалтад нэмнэ (алдаа гарвал энэ дуудлагын
        өмнө/дараа үүссэн бүх move-ийг буцаан ноорог болгоход ашиглана)."""
        move_lines = {}
        debt_debit_account_id = False
        debt_credit_account_id = False

        for obj in unit.line_ids:
            line = obj.sudo()
            if line.rule_id.transaction_type == 'by_partner':
                debt_debit_account_id = line.debit_account_id.id if line.debit_account_id else False
                debt_credit_account_id = line.credit_account_id.id if line.credit_account_id else False
            elif line.rule_id.id not in move_lines:
                move_lines[line.rule_id.id] = {
                    'rule': line.rule_id.id,
                    'debit_sum': 0.0,
                    'credit_sum': 0.0,
                    'debit_account_id': line.debit_account_id.id if line.debit_account_id else False,
                    'credit_account_id': line.credit_account_id.id if line.credit_account_id else False,
                    'internal_type': False,
                    'note': line.transaction_value,
                    'partners': {},
                }

        moves = []
        dbamount = 0.0

        for line in emp_lines:
            cramount = 0.0
            for rule in line.rule_value_ids:
                if rule.payroll_rule_id.id in move_lines:
                    if round(rule.value, 2) != 0.0:
                        move_lines[rule.payroll_rule_id.id]['debit_sum'] += round(rule.value, 2)
                        move_lines[rule.payroll_rule_id.id]['credit_sum'] += round(rule.value, 2)
                        group_partner = line.employee_id.work_contact_id.id
                        partners = move_lines[rule.payroll_rule_id.id]['partners']
                        if group_partner not in partners:
                            partners[group_partner] = {'amount': 0.0, 'partner_id': False, 'name': ''}
                        partners[group_partner]['amount'] += round(rule.value, 2)
                        partners[group_partner]['partner_id'] = group_partner
                        partners[group_partner]['name'] = u'[%s - [%s]' % (
                            move_lines[rule.payroll_rule_id.id]['note'], line.employee_id.name)

                if rule.payroll_rule_id.transaction_type == 'by_partner':
                    cramount += round(rule.value, 2)

            if round(cramount, 2) != 0.0:
                dbamount += round(cramount, 2)
                moves.append((0, 0, {
                    'account_id': debt_credit_account_id,
                    'partner_id': line.employee_id.work_contact_id.id,
                    'name': u'[Цалин харилцагчаар задлах - [%s]' % (line.employee_id.name),
                    'debit': 0.0,
                    'credit': round(cramount, 2),
                }))

        if round(dbamount, 2) != 0.0:
            moves.append((0, 0, {
                'account_id': debt_debit_account_id,
                'partner_id': False,
                'name': u'[Цалин харилцагчаар задлах - %s]' % (department.name if department else unit.name),
                'debit': round(dbamount, 2),
                'credit': 0.0,
            }))

        if moves:
            move_vals = {
                'ref': u'%s [Цалин]' % payroll_id.start_date,
                'line_ids': moves,
                'journal_id': unit.journal_id.id,
                'date': payroll_id.end_date,
            }
            try:
                move_id = self.env['account.move'].create(move_vals)
                mmoves.append(move_id.id)
                self.env['payroll.payment.history'].create({'payroll_id': payroll_id.id, 'move_id': move_id.id})
                self.env.cr.commit()
                move_id.action_post()
            except Exception as e:
                for mmove in mmoves:
                    self.env['account.move'].browse(mmove).button_draft()
                self.env.cr.commit()
                raise UserError(_(u'Алдаа: %s ' % (exception_to_unicode(e))))

        for move in sorted(move_lines.values(), key=itemgetter('rule')):
            if move['debit_sum'] != 0 and move['credit_sum'] != 0:
                rule_moves = self.create_move(move)
                if rule_moves:
                    move_vals = {
                        'ref': u'%s [Цалин]' % payroll_id.start_date,
                        'line_ids': rule_moves,
                        'journal_id': unit.journal_id.id,
                        'date': payroll_id.end_date,
                    }
                    try:
                        move_id = self.env['account.move'].create(move_vals)
                        mmoves.append(move_id.id)
                        self.env['payroll.payment.history'].create({'payroll_id': payroll_id.id, 'move_id': move_id.id})
                        self.env.cr.commit()
                        move_id.action_post()
                    except Exception as e:
                        for mmove in mmoves:
                            self.env['account.move'].browse(mmove).button_draft()
                        self.env.cr.commit()
                        raise UserError(_(u'Алдаа: %s ' % (exception_to_unicode(e))))

    def create_move(self, move):
        moves = []
        if move['internal_type'] == 'credit' or not move['internal_type']:
            moves.append((0, 0, {
                'account_id': move['debit_account_id'],
                'partner_id': False,
                'name': u'[Цалин] %s' % (move['note']),
                'debit': round(move['debit_sum'], 2) > 0 and round(move['debit_sum'], 2),
                'credit': round(move['debit_sum'], 2) < 0 and -1 * round(move['debit_sum'], 2),
            }))

        if move['internal_type'] == 'debit' or not move['internal_type']:
            moves.append((0, 0, {
                'account_id': move['credit_account_id'],
                'partner_id': False,
                'name': u'[Цалин] %s' % (move['note']),
                'debit': round(move['debit_sum'], 2) < 0 and -1 * round(move['debit_sum'], 2),
                'credit': round(move['credit_sum'], 2) > 0 and round(move['credit_sum'], 2),
            }))

        if move['internal_type']:
            for part in sorted(move['partners'].values(), key=itemgetter('partner_id')):
                amount = round(part['amount'], 2) > 0 and round(part['amount'], 2) or -1 * round(part['amount'], 2)
                account = move['internal_type'] == 'debit' and move['debit_account_id'] or move['credit_account_id']
                moves.append((0, 0, {
                    'account_id': account,
                    'partner_id': part['partner_id'],
                    'name': part['name'],
                    'debit': move['internal_type'] == 'debit' and amount or 0.0,
                    'credit': move['internal_type'] == 'credit' and amount or 0.0,
                }))
        return moves


class LLPPayrollAccountMoveLine(models.TransientModel):
    _name = 'llp.payroll.account.move.line'

    no = fields.Integer(string="№")
    account_id = fields.Many2one('account.account', string="Account")
    credit = fields.Float(string="Credit")
    debit = fields.Float(string="Debit")
    amount_currency = fields.Float(string="Amount currency")
    name = fields.Char(String="Name")
    account_move_line_id = fields.Many2one('llp.payroll.account.move', string="Line")
    department_id = fields.Many2one('hr.department', string="Алба нэгж")
    journal_id = fields.Many2one('account.journal', string="Журнал")