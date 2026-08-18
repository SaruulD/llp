/** @odoo-module */

import { Component, onWillStart, onWillUpdateProps } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { standardFieldProps } from "@web/views/fields/standard_field_props";

// Тоон утга бичдэг дүрмийн төрлүүд. Бусад (жишээ нь 'sign') текст утгатай.
const NUMERIC_TYPES = ["digit", "from_previous_payroll"];

class PayrollSheetField extends Component {
  static template = "llp_payroll.PayrollSheetField";
  static props = { ...standardFieldProps };
  static supportedTypes = ["one2many"];

  setup() {
    this.orm = useService("orm");
    this.action = useService("action");

    // 1234567.5 -> "1'234'567.50" (3 оронгоор бүлэглэж, '-аар тусгаарлана)

    this.formatNumber = (val, decimals = 2) => {
      if (val === null || val === undefined || val === false || val === "") {
        return "";
      }
      const n = Number(val);
      if (isNaN(n)) return String(val);

      const fixed = n.toFixed(decimals);
      const negative = fixed.startsWith("-");
      const [intPart, decPart] = (negative ? fixed.slice(1) : fixed).split(".");
      const grouped = intPart.replace(/\B(?=(\d{3})+(?!\d))/g, ",");
      const sign = negative ? "-" : "";

      return decPart !== undefined ? `${sign}${grouped}.${decPart}` : `${sign}${grouped}`;
    };

    // "1'234'567.50" -> 1234567.5  (формат/апостроф арилгаад тоо болгоно)
    this.parseNumber = (raw) => {
      if (typeof raw !== "string") return Number(raw) || 0;
      const cleaned = raw.replace(/'/g, "").trim();
      const n = Number(cleaned);
      return isNaN(n) ? 0 : n;
    };

    // Зөвхөн уншихад зориулсан (view) нүднүүдэд ашиглагдана
    this.formatMoney = (val, rule, decimals) => {
      const rulefieldType = rule[3];
      if (!NUMERIC_TYPES.includes(rulefieldType)) {
        return val === false || val === null || val === undefined ? "" : val;
      }
      return this.formatNumber(val, decimals ?? 2);
    };

    this.goToEmployee = this.goToEmployee.bind(this);
    this.goToRule = this.goToRule.bind(this);
    this.onValueFocus = this.onValueFocus.bind(this);
    this.onValueInput = this.onValueInput.bind(this);
    this.onValueChange = this.onValueChange.bind(this);
    this.onValueKeydown = this.onValueKeydown.bind(this);

    this.state = {
      employees: [],
      rules: [],
      employee_values: {},
      employee_lines: {},
    };

    this.loadData = this.loadData.bind(this);

    onWillStart(async () => {
      await this.loadData(this.props.record?.resId);
    });

    onWillUpdateProps(async (nextProps) => {
      const nextId = nextProps.record?.resId;
      if (nextId !== this.props.record?.resId) {
        await this.loadData(nextId);
      }
    });
  }

  async loadData(sheetId) {
    // Pager-ээр шинэ bичлэг рүү орох эсвэл шинэ (unsaved) bичлэг дээр байх үед
    // хуучин утгыг цэвэрлэнэ, ингэснээр солигдох хооронд хуучин өгөгдөл харагдахгүй
    this.state.employees = [];
    this.state.rules = [];
    this.state.employee_values = {};
    this.state.employee_lines = {};

    if (!sheetId) return;

    const data = await this.orm.call("llp.payroll.line", "get_line_values", [
      sheetId,
    ]);
    Object.assign(this.state, data);
  }

  // Input дээр курсор очиход бүх текстийг сонгоно (дараа нь шууд дарж бичиж болно)
  onValueFocus(ev, rule) {
    if (!NUMERIC_TYPES.includes(rule[3])) return;
    ev.target.select();
  }

  // Бичиж байх явцад (keystroke бүрд) 3 оронгоор нь бүлэглэж форматлана,
  // курсорын байрлалыг тоон орны тоогоор дахин тооцож хадгална.
  onValueInput(ev, rule) {
    if (!NUMERIC_TYPES.includes(rule[3])) return;

    const input = ev.target;
    const cursorPos = input.selectionStart ?? input.value.length;
    const rawBefore = input.value;

    // Курсорын өмнө хэдэн орон (тоо) байсныг тоолно (тусгаарлагчийг оруулахгүй)
    const digitsBeforeCursor = rawBefore.slice(0, cursorPos).replace(/[^\d]/g, "").length;

    // Зөвхөн орон, '.', '-' үлдээнэ
    let cleaned = rawBefore.replace(/[^\d.\-]/g, "");

    // Эхний цэгийг л хадгалж, бусдыг арилгана
    const dotIndex = cleaned.indexOf(".");
    if (dotIndex !== -1) {
      cleaned = cleaned.slice(0, dotIndex + 1) + cleaned.slice(dotIndex + 1).replace(/\./g, "");
    }

    // Хасах тэмдэг зөвхөн эхэнд байж болно
    const negative = cleaned.startsWith("-");
    cleaned = cleaned.replace(/-/g, "");
    if (negative) cleaned = "-" + cleaned;

    const body = negative ? cleaned.slice(1) : cleaned;
    const [intRaw, decRaw] = body.split(".");
    const grouped = (intRaw || "").replace(/\B(?=(\d{3})+(?!\d))/g, "'");

    let formatted = (negative ? "-" : "") + grouped;
    if (decRaw !== undefined) {
      formatted += "." + decRaw;
    } else if (body.endsWith(".")) {
      formatted += ".";
    }

    input.value = formatted;

    // Курсорыг өмнөх тоон орны дараа дахин байрлуулна
    let newPos;
    if (digitsBeforeCursor === 0) {
      newPos = negative ? 1 : 0;
    } else {
      let seen = 0;
      newPos = formatted.length;
      for (let i = 0; i < formatted.length; i++) {
        if (/\d/.test(formatted[i])) {
          seen++;
          if (seen === digitsBeforeCursor) {
            newPos = i + 1;
            break;
          }
        }
      }
    }
    input.setSelectionRange(newPos, newPos);
  }

  // Enter дарахад input-аас гарч, утгыг шууд commit хийнэ
  onValueKeydown(ev) {
    if (ev.key === "Enter") {
      ev.target.blur();
    }
  }

  onValueChange(ev, ruleValueId, empId, ruleId, rule) {
    const raw = ev.target.value;
    const isNumeric = NUMERIC_TYPES.includes(rule[3]);
    const value = isNumeric ? this.parseNumber(raw) : raw;

    // Update UI first
    if (!this.state.employee_values[empId]) {
      this.state.employee_values[empId] = {};
    }
    this.state.employee_values[empId][ruleId] = value;

    // Input-аас гарахад форматласан утгыг харуулна (1'234'567.50)
    if (isNumeric) {
      ev.target.value = this.formatNumber(value, this.state.decimals?.[ruleId] ?? 2);
    }

    // 🔄 RERENDER UI, totals will recompute automatically
    this.render();

    this.orm.call("llp.payroll.line", "update_value", [ruleValueId, value]);
  }

  goToEmployee(id) {
    this.action.doAction({
      type: "ir.actions.act_window",
      res_model: "hr.employee",
      res_id: id,
      views: [[false, "form"]],
    });
  }
  goToRule(id) {
    this.action.doAction({
      type: "ir.actions.act_window",
      res_model: "llp.payroll.rule",
      res_id: id,
      views: [[false, "form"]],
    });
  }
}

registry.category("fields").add("payroll_sheet", {
  component: PayrollSheetField,
  supportedTypes: ["one2many"],
});