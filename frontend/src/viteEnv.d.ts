type ViteEnvOptions = {
    frontendRoot?: string;
    workspaceRoot?: string;
    env?: NodeJS.ProcessEnv;
};
export declare function loadRadiaViteEnv(mode: string, options?: ViteEnvOptions): {
    [x: string]: string | undefined;
};
export {};
