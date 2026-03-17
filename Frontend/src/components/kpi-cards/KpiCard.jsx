import { motion } from "framer-motion";

export function KpiCard({ title, value, change, changeType = "up", icon: Icon }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      whileHover={{ scale: 1.02 }}
      className="rounded-xl bg-[#151619] p-5 card-shadow transition-shadow hover:card-shadow-hover cursor-pointer"
    >
      <div className="flex items-start justify-between">
        <div className="space-y-2">
          <p className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
            {title}
          </p>

          <p className="text-2xl font-bold text-gray-300">
            {value}
          </p>

          {change && (
            <p
              className={`text-xs font-medium ${
                changeType === "up"
                  ? "text-success"
                  : changeType === "down"
                  ? "text-destructive"
                  : "text-muted-foreground"
              }`}
            >
              {change}
            </p>
          )}
        </div>

        {Icon && (
          <div className="rounded-lg bg-white/10 p-2.5">
            <Icon className="h-5 w-5 opacity-70" />
          </div>
        )}
      </div>
    </motion.div>
  );
}
