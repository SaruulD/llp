/** @odoo-module */

import { Component, onWillStart } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { standardFieldProps } from "@web/views/fields/standard_field_props";

class PayrollSheetField extends Component {
  static template = "llp_payroll.PayrollSheetField";
  static props = { ...standardFieldProps };
  static supportedTypes = ["one2many"];

  setup() {
    this.orm = useService("orm");
    this.action = useService("action");
    this.formatMoney = (val, rule, decimals) => {
      if (rule[3] !== "digit" && rule[3] !== "from_previous_payroll") {
        return val === false ? "" : val ?? "";
      }
      if (typeof val === "string") {
        const maybeNum = Number(val);
        if (!isNaN(maybeNum) && val.trim() !== "") {
          return maybeNum.toLocaleString(undefined, {
            minimumFractionDigits: decimals,
            maximumFractionDigits: decimals,
          });
        }
        return val;
      }

      if (typeof val === "number" && !isNaN(val)) {
        const n = Number(val) || 0;
        return n.toLocaleString(undefined, {
          minimumFractionDigits: decimals,
          maximumFractionDigits: decimals,
        });
      }

      return val ?? "";
    };

    this.goToEmployee = this.goToEmployee.bind(this);
    this.goToRule = this.goToRule.bind(this);
    this.onValueChange = this.onValueChange.bind(this);

    this.state = {
      employees: [],
      rules: [],
      employee_values: {},
      employee_lines: {},
    };

    onWillStart(async () => {
      const sheetId = this.props.record?.resId;
      if (!sheetId) return;
      const data = await this.orm.call("llp.payroll.line", "get_line_values", [
        sheetId,
      ]);
      Object.assign(this.state, data);
    });
  }

  onValueChange(ev, ruleValueId, empId, ruleId) {
    const raw = ev.target.value;

    const sheetState = this.props.record.data.state;

    // Update UI first
    if (!this.state.employee_values[empId]) {
      this.state.employee_values[empId] = {};
    }

    const numeric = Number(raw) || 0;
    this.state.employee_values[empId][ruleId] = numeric;

    // 🔄 RERENDER UI, totals will recompute automatically
    this.render();

    this.orm.call("llp.payroll.line", "update_value", [ruleValueId, raw]);
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
