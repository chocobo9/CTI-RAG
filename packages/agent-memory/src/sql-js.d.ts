declare module "sql.js" {
	interface SqlStatement {
		bind(values?: readonly unknown[]): void;
		step(): boolean;
		getAsObject(): Record<string, unknown>;
		free(): void;
	}
	export interface SqlDatabase {
		exec(sql: string): void;
		prepare(sql: string): SqlStatement;
		export(): Uint8Array;
	}
	interface SqlJsStatic {
		Database: new (data?: Uint8Array) => SqlDatabase;
	}
	interface SqlJsOptions {
		locateFile: (file: string) => string;
	}
	const initSqlJs: (options: SqlJsOptions) => Promise<SqlJsStatic>;
	export default initSqlJs;
}
