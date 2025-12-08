import * as d3 from "d3";
import * as Plot from "@observablehq/plot";
export function filterErrors(data) {
    let errors = [];
    let normal = [];
    for (let r of data) {
        if (r.error !== undefined || r.modelName === undefined) {
            errors.push(r);
            continue;
        }
        normal.push(r);
    }
    return [normal, errors];
}
export function computePairs(dataA, dataB) {
    let workingPairs = [];
    // Find matching pairs benchmark runs
    for (let a of dataA) {
        for (let b of dataB) {
            if (a.modelName === b.modelName)
                workingPairs.push({ a: a, b: b, modelName: a.modelName });
        }
    }
    return workingPairs;
}
export function computeSinglePair(modelName, dataA, dataB) {
    let a = dataA.find((r) => r.modelName === modelName);
    let b = dataB.find((r) => r.modelName === modelName);
    if (!a || !b || a.error !== undefined || b.error !== undefined)
        return undefined;
    return { a: a, b: b, modelName: modelName };
}
// Fields is an object in the form { label1: "field1", label2: "field2" }.
// Where field is either a name of the field in NormalBenchmarkResult or it is a function to call on pair.
// For each pair field, name the tip will show:
//   * For simple field: "label: pair.a.field \n label: pair.b.field"
//   * For function field: "label: field(pair.a)"
export function formatTip(pair, fields, runNames) {
    let result = pair.modelName + "\n";
    for (let label in fields) {
        let field = fields[label];
        if (typeof field === "function") {
            result += "\n";
            if (label != "")
                result += label + ": ";
            result += field(pair);
        }
        else {
            let valA = pair.a[field];
            let valB = pair.b[field];
            let a = valA === undefined ? "None" : d3.format(".4s")(valA);
            let b = valB === undefined ? "None" : d3.format(".4s")(valB);
            result += "\n" + label + " " + runNames[0] + ": " + a +
                "\n" + label + " " + runNames[1] + ": " + b;
        }
    }
    return result;
}
// Color for highlighting the bar under the mouse:
const highlightColor = "red";
// "Diverging bars" plot inspired by:
//    https://observablehq.com/@observablehq/plot-state-population-change
// Makes the plot based on pair.field. Tooltip contains pair.field labeled as
// fieldLabel. Additional fields my be added to the tip (for mouse over), see
// formatTip.
// Options could be:
//   percentage: boolean, whether to interpret field as percentage (default false)
export function divergingBars(runNames, pairs, yName, yFunc, tipFields, options = {}) {
    return Plot.plot({
        label: null,
        marginLeft: 100,
        // width: 800,
        // height: 500,
        y: {
            axis: "left",
            labelAnchor: "center",
            tickFormat: options.percentage ? "%" : ".2s",
            label: yName,
        },
        color: {
            scheme: "PRGn",
            type: "ordinal",
            domain: [-1, 0, 1]
        },
        marks: [
            Plot.barY(pairs, {
                x: "modelName",
                y: yFunc,
                fill: (pair) => Math.sign((yFunc(pair) ?? 0)),
                sort: { x: "y", reverse: true },
                // Href points to instance.html with modelName variable set to pair.modelName:
                href: (pair) => encodeURIComponent(pair.modelName + ".html"),
                target: "_blank",
            }),
            // Highlight the bar under the mouse:
            Plot.barY(pairs, Plot.pointerX({
                x: "modelName",
                y: yFunc,
                fill: (_) => highlightColor,
                sort: { x: "y", reverse: true },
                pointerEvents: "none",
            })),
            Plot.gridY({ stroke: "white", strokeOpacity: 0.5 }),
            Plot.axisX({
                y: 0,
                tickRotate: 90,
                ticks: (pairs.length > 30 ? [] : undefined),
                // Make the axis labels "transparent" for the mouse. This way mouse
                // clicks go through to the bars (the labels may overlap the bars and
                // then the clicks would not work).
                pointerEvents: "none"
            }),
            Plot.ruleY([0]),
            Plot.tip(pairs, Plot.pointerX({
                x: "modelName",
                y: (pair) => (yFunc(pair) ?? 0) / 2,
                title: (d) => formatTip(d, tipFields, runNames)
            })),
            // Plot.text(pairs, Plot.pointerX({
            //   px: "modelName",
            //   dy: -17,
            //   frameAnchor: "top-left",
            //   fontVariant: "tabular-nums",
            //   text: (d) => "modelName"
            // })),
        ]
    });
}
export function format(num) {
    if (num === undefined)
        return "";
    if (Math.abs(num) <= 1000 && Number.isInteger(num))
        return "" + num;
    return d3.format(".4s")(num);
}
export function formatDuration(num) {
    if (num === undefined)
        return "None";
    if (num >= 60) {
        let m = Math.floor(num / 60);
        let s = num - m * 60;
        if (m > 0 && s < 0.005) {
            // We can use minutes and ignore seconds
            let h = Math.floor(m / 60);
            m = m - h * 60;
            if (h > 0 && m == 0) {
                // We can use hours and ignore minutes
                return d3.format(".0f")(h) + "h";
            }
            return d3.format(".0f")(m) + "min";
        }
    }
    if (num >= 1)
        return d3.format(".2f")(num) + "s";
    if (num == 0)
        return "0s";
    return d3.format(".3s")(num) + "s";
}
export function formatDurationDiff(a, b) {
    if (a === undefined || b === undefined)
        return "";
    let num = b - a;
    return (num > 0 ? "+" : "") + formatDuration(num);
}
export function absoluteDiff(a, b) {
    if (a === undefined || b === undefined)
        return undefined;
    return b - a;
}
export function formatAbsoluteDiff(a, b) {
    let d = absoluteDiff(a, b);
    if (d === undefined)
        return "";
    let prefix = d > 0 ? "+" : "";
    if (Number.isInteger(d) && Math.abs(d) < 1000)
        return prefix + d;
    return prefix + d3.format(".4s")(d);
}
export function relativeDiff(a, b) {
    if (a === undefined || b === undefined)
        return undefined;
    if (a == b)
        return 0;
    if (a == 0)
        return undefined;
    return (b - a) / a;
}
export function formatRelativeDiff(a, b) {
    let d = relativeDiff(a, b);
    if (d === undefined)
        return "";
    if (d == 0)
        return "0%";
    return d3.format("+.3%")(d);
}
export function objectiveDiff(vA, vB) {
    if (typeof vA != "number" || typeof vB != "number")
        return undefined;
    return vB - vA;
}
export function relativeObjectiveDiff(vA, vB) {
    if (typeof vA != "number" || typeof vB != "number")
        return undefined;
    return relativeDiff(vA, vB);
}
export function formatObjectiveDiff(vA, vB) {
    if (typeof vA != "number" || typeof vB != "number")
        return "";
    let diff = vB - vA;
    if (diff == 0)
        return "0";
    return d3.format("+")(diff);
}
export function formatRelativeObjectiveDiff(vA, vB) {
    let d = relativeObjectiveDiff(vA, vB);
    if (d === undefined)
        return "";
    if (d == 0)
        return "0";
    return d3.format("+.3%")(d);
}
export function formatObjective(value) {
    if (value === undefined)
        return "None";
    if (value == null)
        return "absent";
    if (typeof value == "number")
        return d3.format("")(value);
    let result = "[";
    for (let i = 0; i < value.length; ++i) {
        if (i > 0)
            result += ", ";
        let v = value[i];
        if (v === null)
            result += "absent";
        else
            result += "" + v;
    }
    result += "]";
    return result;
}
export function objectiveForSort(value) {
    if (value === undefined)
        return "";
    if (Array.isArray(value))
        return "";
    return "" + value;
}
export function areObjectivesSame(a, b) {
    if (a === b)
        return true;
    if (!Array.isArray(a) || !Array.isArray(b))
        return false;
    for (let i = 0; i < a.length; ++i) {
        if (a[i] !== b[i])
            return false;
    }
    return true;
}
export function formatStatus(r) {
    if (r.error !== undefined)
        return "Error";
    if (r.nbSolutions == 0) {
        if (r.proof)
            return "Infeasible";
        return "No solution";
    }
    if (r.proof)
        return "Optimum";
    return "Solution";
}
export function formatMemory(bytes) {
    if (bytes < 1024)
        return d3.format(".0f")(bytes) + "B";
    bytes /= 1024;
    // We compare with 1000, not 1024, because e.g. 1021.64kB looks strange.
    if (bytes < 1000)
        return d3.format(".2f")(bytes) + "KB";
    bytes /= 1024;
    if (bytes < 1000)
        return d3.format(".2f")(bytes) + "MB";
    bytes /= 1024;
    return d3.format(".2f")(bytes) + "GB";
}
export function formatDeltaMemory(a, b) {
    if (a == b)
        return "0";
    return (b >= a ? "+" : "-") + formatMemory(Math.abs(b - a));
}
