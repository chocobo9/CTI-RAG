import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const materializedSchema: unknown = require("./schemas/orientation-materialized-v2.schema.json");
const observationSchema: unknown = require("./schemas/orientation-observation-v1.schema.json");

type JsonObject = Readonly<Record<string, unknown>>;

function isObject(value: unknown): value is JsonObject {
	return typeof value === "object" && value !== null && !Array.isArray(value);
}

function hasValidUnicode(value: string): boolean {
	for (let index = 0; index < value.length; index++) {
		const codeUnit = value.charCodeAt(index);
		if (codeUnit >= 0xd800 && codeUnit <= 0xdbff) {
			const next = value.charCodeAt(index + 1);
			if (next < 0xdc00 || next > 0xdfff) return false;
			index++;
		} else if (codeUnit >= 0xdc00 && codeUnit <= 0xdfff) {
			return false;
		}
	}
	return true;
}

function hasValidJsonDomain(value: unknown): boolean {
	if (value === null || typeof value === "boolean") return true;
	if (typeof value === "string") return hasValidUnicode(value);
	if (typeof value === "number") return Number.isFinite(value) && Number.isSafeInteger(value);
	if (Array.isArray(value)) return value.every(hasValidJsonDomain);
	if (!isObject(value)) return false;
	return Object.entries(value).every(([key, child]) => hasValidUnicode(key) && hasValidJsonDomain(child));
}

function resolvePointer(root: JsonObject, pointer: string): unknown {
	let current: unknown = root;
	for (const encodedSegment of pointer.split("/").slice(1)) {
		if (!isObject(current)) return undefined;
		const segment = encodedSegment.replaceAll("~1", "/").replaceAll("~0", "~");
		current = current[segment];
	}
	return current;
}

function resolveReference(
	reference: string,
	currentRoot: JsonObject,
): { schema: unknown; root: JsonObject } | undefined {
	if (reference.startsWith("#")) {
		return { schema: resolvePointer(currentRoot, reference.slice(1)), root: currentRoot };
	}
	const [resource, fragment = ""] = reference.split("#", 2);
	if (resource !== "orientation-observation-v1.schema.json") return undefined;
	const root = observationSchema as JsonObject;
	return { schema: resolvePointer(root, fragment), root };
}

function matchesType(type: unknown, value: unknown): boolean {
	if (type === "object") return isObject(value);
	if (type === "array") return Array.isArray(value);
	if (type === "string") return typeof value === "string";
	if (type === "boolean") return typeof value === "boolean";
	return false;
}

function matchesSchema(schemaValue: unknown, value: unknown, root: JsonObject): boolean {
	if (!isObject(schemaValue)) return false;
	const reference = schemaValue.$ref;
	if (typeof reference === "string") {
		const resolved = resolveReference(reference, root);
		return resolved !== undefined && matchesSchema(resolved.schema, value, resolved.root);
	}
	const alternatives = schemaValue.oneOf;
	if (Array.isArray(alternatives)) {
		return alternatives.filter((candidate) => matchesSchema(candidate, value, root)).length === 1;
	}
	if ("const" in schemaValue && !Object.is(schemaValue.const, value)) return false;
	if (Array.isArray(schemaValue.enum) && !schemaValue.enum.some((candidate) => Object.is(candidate, value)))
		return false;
	if (schemaValue.type !== undefined && !matchesType(schemaValue.type, value)) return false;
	if (typeof value === "string") {
		if (typeof schemaValue.minLength === "number" && value.length < schemaValue.minLength) return false;
		if (typeof schemaValue.pattern === "string" && !new RegExp(schemaValue.pattern, "u").test(value)) return false;
	}
	if (Array.isArray(value)) {
		return schemaValue.items === undefined || value.every((item) => matchesSchema(schemaValue.items, item, root));
	}
	if (!isObject(value)) return true;
	const properties = isObject(schemaValue.properties) ? schemaValue.properties : {};
	if (Array.isArray(schemaValue.required)) {
		for (const required of schemaValue.required) {
			if (typeof required !== "string" || !Object.hasOwn(value, required)) return false;
		}
	}
	if (schemaValue.additionalProperties === false) {
		for (const key of Object.keys(value)) {
			if (!Object.hasOwn(properties, key)) return false;
		}
	}
	for (const [key, child] of Object.entries(value)) {
		const propertySchema = properties[key];
		if (propertySchema !== undefined && !matchesSchema(propertySchema, child, root)) return false;
	}
	return true;
}

function validates(schema: JsonObject, value: unknown): boolean {
	return hasValidJsonDomain(value) && matchesSchema(schema, value, schema);
}

export function validatesOrientationObservation(value: unknown): boolean {
	return validates(observationSchema as JsonObject, value);
}

export function validatesMaterializedOrientation(value: unknown): boolean {
	return validates(materializedSchema as JsonObject, value);
}
