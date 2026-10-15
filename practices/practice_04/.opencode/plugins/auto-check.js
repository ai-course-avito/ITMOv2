export const AutoCheckPlugin = async ({ $, directory }) => {
  return {
    event: async ({ event }) => {
      if (event.type !== "file.edited") {
        return;
      }

      console.log("[auto-check] Файл изменён. Запускаю проверку...");

      try {
        await $`npm run check`.cwd(directory);

        console.log(
          "[auto-check] Project checks passed."
        );
      } catch (error) {
        console.error(
          "[auto-check] Project checks failed."
        );

        throw error;
      }
    }
  };
};